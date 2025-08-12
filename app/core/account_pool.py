# account_pool.py
"""
Pool de contas Instagram com gerenciamento inteligente
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pathlib import Path
import random

from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired, UserNotFound

from app.models import InstagramAccount, AccountStatus
from app.config import Settings

logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent.parent

class AccountPool:
    """
    Gerenciador inteligente de pool de contas Instagram
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.accounts: List[InstagramAccount] = []
        self.clients: Dict[str, Client] = {}
        self._pool_file = project_root / "data" / "account_pool.json"
        
        # Criar diretórios necessários
        Path(settings.session_dir).mkdir(exist_ok=True)
        Path(settings.downloads_dir).mkdir(exist_ok=True)
        
        # Carregar pool existente
        self._load_pool()
        
        logger.info(f"AccountPool inicializado com {len(self.accounts)} contas")
    
    def add_account(self, username: str, password: str, proxy: Optional[str] = None) -> bool:
        """
        Adiciona nova conta ao pool
        
        Args:
            username: Nome de usuário
            password: Senha
            proxy: Proxy opcional
            
        Returns:
            bool: True se adicionada com sucesso
        """
        try:
            # Verificar se já existe
            if any(acc.username == username for acc in self.accounts):
                logger.warning(f"Conta {username} já existe no pool")
                return False
            
            # Criar conta
            session_file = os.path.join(self.settings.session_dir, f"{username}_session.json")
            account = InstagramAccount(
                username=username,
                password=password,
                proxy=proxy,
                session_file=session_file
            )
            
            # Testar login
            if self._test_account_login(account):
                self.accounts.append(account)
                self._save_pool()
                # Log seguro sem emojis no Windows
                import sys
                if sys.platform == "win32":
                    logger.info(f"[OK] Conta {username} adicionada ao pool")
                else:
                    logger.info(f"✅ Conta {username} adicionada ao pool")
                return True
            else:
                if sys.platform == "win32":
                    logger.error(f"[ERROR] Falha no teste de login para {username}")
                else:
                    logger.error(f"❌ Falha no teste de login para {username}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao adicionar conta {username}: {e}")
            return False
    
    def _test_account_login(self, account: InstagramAccount) -> bool:
        """
        Testa login da conta
        
        Args:
            account: Conta para testar
            
        Returns:
            bool: True se login bem-sucedido
        """
        try:
            client = Client()
            
            # Configurar delays
            client.delay_range = [self.settings.request_delay_min, self.settings.request_delay_max]
            
            # Configurar proxy se fornecido
            if account.proxy:
                client.set_proxy(account.proxy)
            
            # Tentar carregar sessão existente
            if os.path.exists(account.session_file):
                try:
                    client.load_settings(account.session_file)
                    client.login(account.username, account.password)
                    client.get_timeline_feed()  # Teste de validação
                    logger.info(f"Login via sessão bem-sucedido: {account.username}")
                    return True
                except LoginRequired:
                    logger.info(f"Sessão inválida para {account.username}, fazendo novo login")
            
            # Login novo
            if client.login(account.username, account.password):
                client.dump_settings(account.session_file)
                logger.info(f"Novo login bem-sucedido: {account.username}")
                return True
                
        except ChallengeRequired:
            logger.warning(f"Challenge requerido para {account.username}")
            account.status = AccountStatus.CHALLENGE
        except Exception as e:
            logger.error(f"Erro no teste de login {account.username}: {e}")
            account.status = AccountStatus.DEAD
        
        return False
    
    def get_available_account(self) -> Optional[InstagramAccount]:
        """
        Obtém conta disponível do pool com algoritmo inteligente e debug aprimorado
        
        Returns:
            InstagramAccount ou None se nenhuma disponível
        """
        logger.info(f"Verificando contas disponíveis no pool de {len(self.accounts)} contas")
        
        # DEBUG: Verificar cada conta individualmente
        available_accounts = []
        for i, acc in enumerate(self.accounts):
            logger.info(f"Conta {i+1}: {acc.username} - Status: {acc.status}")
            
            # CORREÇÃO: Implementar is_available() manualmente se método falhar
            try:
                is_available = acc.is_available()
                logger.info(f"  - is_available() retornou: {is_available}")
            except Exception as e:
                logger.warning(f"  - is_available() falhou: {e}")
                # Fallback: verificar manualmente
                is_available = self._is_account_available_fallback(acc)
                logger.info(f"  - fallback is_available: {is_available}")
            
            if is_available:
                available_accounts.append(acc)
                logger.info(f"  - ✅ Conta {acc.username} adicionada à lista de disponíveis")
            else:
                logger.info(f"  - ❌ Conta {acc.username} não está disponível")
        
        logger.info(f"Total de contas disponíveis encontradas: {len(available_accounts)}")
        
        if not available_accounts:
            logger.warning("Nenhuma conta disponível no pool")
            
            # DEBUG: Tentar forçar uma conta ACTIVE mesmo que is_available() seja False
            logger.info("Tentando fallback - procurando contas ACTIVE...")
            for acc in self.accounts:
                if acc.status == AccountStatus.ACTIVE:
                    logger.warning(f"FALLBACK: Usando conta {acc.username} que está ACTIVE mas is_available()=False")
                    return acc
            
            return None
        
        # Algoritmo de seleção: peso baseado em health score e tempo de última utilização
        def calculate_score(account: InstagramAccount) -> float:
            health_weight = account.health_score / 100.0
            
            # Peso temporal - contas não usadas recentemente têm prioridade
            if account.last_used:
                hours_since_last_use = (datetime.now() - account.last_used).total_seconds() / 3600
                time_weight = min(1.0, hours_since_last_use / 24)  # Máximo 1.0 após 24h
            else:
                time_weight = 1.0
            
            # Peso de utilização - contas menos usadas hoje têm prioridade
            usage_weight = 1.0 - (account.operations_today / self.settings.max_daily_operations_per_account)
            
            return (health_weight * 0.4) + (time_weight * 0.4) + (usage_weight * 0.2)
        
        # Selecionar conta com maior score
        best_account = max(available_accounts, key=calculate_score)
        
        logger.info(f"Conta selecionada: {best_account.username} (health: {best_account.health_score:.1f})")
        return best_account
    
    def _is_account_available_fallback(self, account: InstagramAccount) -> bool:
        """
        Implementação fallback para verificar se conta está disponível
        
        Args:
            account: Conta para verificar
            
        Returns:
            bool: True se disponível
        """
        try:
            # Verificar status básico
            if account.status != AccountStatus.ACTIVE:
                return False
            
            # Verificar limite diário
            if account.operations_today >= self.settings.max_daily_operations_per_account:
                return False
            
            # Verificar cooldown
            if account.last_used:
                cooldown_time = timedelta(minutes=self.settings.account_cooldown_minutes)
                if datetime.now() - account.last_used < cooldown_time:
                    return False
            
            # Se passou em todos os testes, está disponível
            return True
            
        except Exception as e:
            logger.error(f"Erro no fallback is_available para {account.username}: {e}")
            return False
    
    def get_client(self, account: InstagramAccount) -> Optional[Client]:
        """
        Obtém cliente configurado para a conta
        
        Args:
            account: Conta Instagram
            
        Returns:
            Client configurado ou None se erro
        """
        try:
            # Verificar se já existe cliente para esta conta
            if account.username in self.clients:
                client = self.clients[account.username]
                try:
                    # Testar se cliente ainda está válido
                    client.get_timeline_feed()
                    return client
                except:
                    # Cliente inválido, remover do cache
                    del self.clients[account.username]
            
            # Criar novo cliente
            client = Client()
            client.delay_range = [self.settings.request_delay_min, self.settings.request_delay_max]
            
            if account.proxy:
                client.set_proxy(account.proxy)
            
            # Login
            if os.path.exists(account.session_file):
                client.load_settings(account.session_file)
            
            client.login(account.username, account.password)
            
            # Cache cliente
            self.clients[account.username] = client
            
            return client
            
        except Exception as e:
            logger.error(f"Erro ao obter cliente para {account.username}: {e}")
            account.update_health_score(False)
            
            if isinstance(e, ChallengeRequired):
                account.status = AccountStatus.CHALLENGE
            elif isinstance(e, LoginRequired):
                account.status = AccountStatus.LOGIN_REQUIRED
            else:
                account.status = AccountStatus.DEAD
            
            self._save_pool()
            return None
    
    def mark_account_used(self, account: InstagramAccount, success: bool = True):
        """
        Marca conta como usada e atualiza métricas
        
        Args:
            account: Conta usada
            success: Se a operação foi bem-sucedida
        """
        account.mark_used()
        account.update_health_score(success)
        
        # Verificar se deve entrar em cooldown
        if account.operations_today >= self.settings.max_daily_operations_per_account:
            account.status = AccountStatus.COOLDOWN
            logger.info(f"Conta {account.username} em cooldown - limite diário atingido")
        
        self._save_pool()
    
    def health_check(self):
        """
        Verifica saúde de todas as contas e atualiza status
        """
        logger.info("Iniciando health check das contas...")
        
        for account in self.accounts:
            try:
                # Reset daily operations se necessário
                if account.last_used and account.last_used.date() < datetime.now().date():
                    account.operations_today = 0
                    if account.status == AccountStatus.COOLDOWN:
                        account.status = AccountStatus.ACTIVE
                
                # Verificar contas em cooldown
                if account.status == AccountStatus.COOLDOWN:
                    if account.last_used:
                        cooldown_time = timedelta(minutes=self.settings.account_cooldown_minutes)
                        if datetime.now() - account.last_used >= cooldown_time:
                            account.status = AccountStatus.ACTIVE
                            logger.info(f"Conta {account.username} saiu do cooldown")
                
                # Tentar recuperar contas com problemas
                if account.status in [AccountStatus.CHALLENGE, AccountStatus.LOGIN_REQUIRED]:
                    if account.health_score > 50:  # Só tenta recuperar contas com score razoável
                        if self._test_account_login(account):
                            account.status = AccountStatus.ACTIVE
                            logger.info(f"Conta {account.username} recuperada!")
                
            except Exception as e:
                logger.error(f"Erro no health check da conta {account.username}: {e}")
        
        self._save_pool()
        logger.info("Health check concluído")
    
    def get_pool_status(self) -> Dict:
        """
        Retorna status detalhado do pool
        
        Returns:
            Dict com estatísticas do pool
        """
        status_counts = {}
        for status in AccountStatus:
            status_counts[status.value] = len([acc for acc in self.accounts if acc.status == status])
        
        # CORREÇÃO: Usar fallback para contar contas disponíveis
        available_count = 0
        for acc in self.accounts:
            try:
                if acc.is_available():
                    available_count += 1
            except:
                if self._is_account_available_fallback(acc):
                    available_count += 1
        
        avg_health = sum(acc.health_score for acc in self.accounts) / len(self.accounts) if self.accounts else 0
        
        return {
            "total_accounts": len(self.accounts),
            "available_accounts": available_count,
            "status_breakdown": status_counts,
            "average_health_score": round(avg_health, 2),
            "total_operations_today": sum(acc.operations_today for acc in self.accounts),
            "last_health_check": datetime.now().isoformat()
        }
    
    def _load_pool(self):
        """Carrega pool de contas do arquivo"""
        try:
            if os.path.exists(self._pool_file):
                with open(self._pool_file, 'r') as f:
                    data = json.load(f)
                    self.accounts = [InstagramAccount(**acc_data) for acc_data in data]
                logger.info(f"Pool carregado: {len(self.accounts)} contas")
            else:
                logger.info("Arquivo de pool não existe, iniciando com pool vazio")
        except Exception as e:
            logger.error(f"Erro ao carregar pool: {e}")
            self.accounts = []
    
    def _save_pool(self):
        """Salva pool de contas no arquivo"""
        try:
            # Criar diretório se não existir
            os.makedirs(os.path.dirname(self._pool_file), exist_ok=True)
            
            data = [acc.dict() for acc in self.accounts]
            with open(self._pool_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Erro ao salvar pool: {e}")
    
    def remove_account(self, username: str) -> bool:
        """
        Remove conta do pool
        
        Args:
            username: Nome de usuário para remover
            
        Returns:
            bool: True se removida com sucesso
        """
        for i, account in enumerate(self.accounts):
            if account.username == username:
                # Remover cliente do cache
                if username in self.clients:
                    del self.clients[username]
                
                # Remover arquivo de sessão
                if os.path.exists(account.session_file):
                    os.remove(account.session_file)
                
                # Remover da lista
                del self.accounts[i]
                self._save_pool()
                
                logger.info(f"Conta {username} removida do pool")
                return True
        
        logger.warning(f"Conta {username} não encontrada no pool")
        return False