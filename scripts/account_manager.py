#!/usr/bin/env python3
"""
Script para gerenciar contas do pool de forma fácil
Execute este arquivo para adicionar/remover/visualizar contas
"""

import asyncio
import sys
import os
from typing import List, Tuple

# Adicionar raiz do projeto ao path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Imports corrigidos
from app.config import Settings
from app.models import InstagramAccount, AccountStatus
from app.utils.logging_config import setup_logging
from app.core.account_pool import AccountPool


class AccountManager:
    """Gerenciador simples para contas do pool"""
    
    def __init__(self):
        self.settings = Settings()
        setup_logging(self.settings)
        self.pool = AccountPool(self.settings)
    
    def show_menu(self):
        """Exibe menu principal"""
        print("\n" + "="*60)
        print("🏊‍♂️ GERENCIADOR DE CONTAS INSTAGRAM")
        print("="*60)
        print("1. 📊 Ver status do pool")
        print("2. ➕ Adicionar conta")
        print("3. ➕ Adicionar múltiplas contas")
        print("4. ❌ Remover conta")
        print("5. 🏥 Health check")
        print("6. 🧪 Testar conta específica")
        print("7. 📋 Listar todas as contas")
        print("8. 🚪 Sair")
        print("="*60)
    
    def show_pool_status(self):
        """Mostra status detalhado do pool"""
        status = self.pool.get_pool_status()
        
        print("\n📊 STATUS DO POOL:")
        print("-" * 40)
        print(f"Total de contas: {status['total_accounts']}")
        print(f"Contas disponíveis: {status['available_accounts']}")
        print(f"Score médio de saúde: {status['average_health_score']}")
        print(f"Operações hoje: {status['total_operations_today']}")
        
        print("\n📈 BREAKDOWN POR STATUS:")
        for status_name, count in status['status_breakdown'].items():
            emoji = self._get_status_emoji(status_name)
            print(f"  {emoji} {status_name.title()}: {count}")
    
    def _get_status_emoji(self, status: str) -> str:
        """Retorna emoji para status"""
        emojis = {
            'active': '✅',
            'cooldown': '⏱️',
            'dead': '💀',
            'challenge': '🚫',
            'login_required': '🔐'
        }
        return emojis.get(status, '❓')
    
    def add_single_account(self):
        """Adiciona uma conta individual"""
        print("\n➕ ADICIONAR CONTA")
        print("-" * 20)
        
        username = input("👤 Username Instagram: ").strip()
        if not username:
            print("❌ Username é obrigatório!")
            return
        
        password = input("🔐 Password: ").strip()
        if not password:
            print("❌ Password é obrigatório!")
            return
        
        proxy = input("🌐 Proxy (opcional - enter para pular): ").strip()
        proxy = proxy if proxy else None
        
        print(f"\n🔄 Testando conta {username}...")
        
        success = self.pool.add_account(username, password, proxy)
        
        if success:
            print(f"✅ Conta {username} adicionada com sucesso!")
        else:
            print(f"❌ Falha ao adicionar conta {username}")
            print("💡 Verifique as credenciais e tente novamente")
    
    def add_multiple_accounts(self):
        """Adiciona múltiplas contas de uma vez"""
        print("\n➕ ADICIONAR MÚLTIPLAS CONTAS")
        print("-" * 30)
        print("💡 Digite as contas no formato: username:password ou username:password:proxy")
        print("💡 Uma conta por linha. Digite 'fim' para terminar.")
        print()
        
        accounts = []
        while True:
            line = input("Conta (username:password:proxy): ").strip()
            
            if line.lower() == 'fim':
                break
            
            if not line:
                continue
            
            parts = line.split(':')
            if len(parts) < 2:
                print("❌ Formato inválido! Use username:password ou username:password:proxy")
                continue
            
            username = parts[0].strip()
            password = parts[1].strip()
            proxy = parts[2].strip() if len(parts) > 2 else None
            
            accounts.append((username, password, proxy))
            print(f"✅ {username} adicionado à lista")
        
        if not accounts:
            print("❌ Nenhuma conta para adicionar")
            return
        
        print(f"\n🔄 Adicionando {len(accounts)} contas...")
        
        success_count = 0
        for username, password, proxy in accounts:
            print(f"Testando {username}... ", end="")
            
            if self.pool.add_account(username, password, proxy):
                print("✅")
                success_count += 1
            else:
                print("❌")
        
        print(f"\n📊 Resultado: {success_count}/{len(accounts)} contas adicionadas com sucesso")
    
    def remove_account(self):
        """Remove uma conta do pool"""
        self.list_accounts()
        
        print("\n❌ REMOVER CONTA")
        print("-" * 15)
        
        username = input("👤 Username para remover: ").strip()
        if not username:
            print("❌ Username é obrigatório!")
            return
        
        confirm = input(f"⚠️ Tem certeza que quer remover '{username}'? (s/N): ").strip().lower()
        if confirm not in ['s', 'sim', 'y', 'yes']:
            print("❌ Operação cancelada")
            return
        
        if self.pool.remove_account(username):
            print(f"✅ Conta {username} removida com sucesso!")
        else:
            print(f"❌ Conta {username} não encontrada!")
    
    def health_check(self):
        """Executa health check do pool"""
        print("\n🏥 EXECUTANDO HEALTH CHECK...")
        print("-" * 30)
        
        self.pool.health_check()
        print("✅ Health check concluído!")
        
        # Mostrar status atualizado
        self.show_pool_status()
    
    def test_specific_account(self):
        """Testa uma conta específica"""
        self.list_accounts()
        
        print("\n🧪 TESTAR CONTA")
        print("-" * 15)
        
        username = input("👤 Username para testar: ").strip()
        if not username:
            print("❌ Username é obrigatório!")
            return
        
        # Encontrar conta
        account = None
        for acc in self.pool.accounts:
            if acc.username == username:
                account = acc
                break
        
        if not account:
            print(f"❌ Conta {username} não encontrada!")
            return
        
        print(f"🔄 Testando conta {username}...")
        
        # Tentar obter cliente
        client = self.pool.get_client(account)
        
        if client:
            try:
                # Teste básico
                timeline = client.get_timeline_feed()
                print(f"✅ Conta {username} está funcionando!")
                print(f"📊 Health score: {account.health_score}")
                print(f"📈 Operações hoje: {account.operations_today}")
                print(f"🎯 Status: {account.status}")
            except Exception as e:
                print(f"❌ Erro no teste: {e}")
                account.update_health_score(False)
        else:
            print(f"❌ Não foi possível obter cliente para {username}")
    
    def list_accounts(self):
        """Lista todas as contas do pool"""
        print("\n📋 LISTA DE CONTAS")
        print("-" * 50)
        
        if not self.pool.accounts:
            print("📭 Nenhuma conta no pool")
            return
        
        for i, account in enumerate(self.pool.accounts, 1):
            emoji = self._get_status_emoji(account.status)
            available = "🟢" if account.is_available() else "🔴"
            
            print(f"{i:2d}. {emoji} {account.username}")
            print(f"     Status: {account.status} {available}")
            print(f"     Health: {account.health_score:.1f}")
            print(f"     Ops hoje: {account.operations_today}")
            print(f"     Último uso: {account.last_used or 'Nunca'}")
            print()
    
    async def run(self):
        """Loop principal do gerenciador"""
        print("🚀 Inicializando gerenciador de contas...")
        
        # Mostrar status inicial
        self.show_pool_status()
        
        while True:
            try:
                self.show_menu()
                choice = input("\n👉 Escolha uma opção: ").strip()
                
                if choice == '1':
                    self.show_pool_status()
                elif choice == '2':
                    self.add_single_account()
                elif choice == '3':
                    self.add_multiple_accounts()
                elif choice == '4':
                    self.remove_account()
                elif choice == '5':
                    self.health_check()
                elif choice == '6':
                    self.test_specific_account()
                elif choice == '7':
                    self.list_accounts()
                elif choice == '8':
                    print("\n👋 Saindo...")
                    break
                else:
                    print("❌ Opção inválida! Tente novamente.")
                
                # Pausa para ler resultado
                if choice != '8':
                    input("\n⏸️ Pressione Enter para continuar...")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Saindo...")
                break
            except Exception as e:
                print(f"\n❌ Erro inesperado: {e}")
                input("⏸️ Pressione Enter para continuar...")


# Script de exemplo para adicionar contas em batch
def add_accounts_from_file():
    """
    Função para adicionar contas de um arquivo
    Crie um arquivo 'accounts.txt' com formato:
    username1:password1
    username2:password2:proxy2
    """
    try:
        settings = Settings()
        setup_logging(settings)
        pool = AccountPool(settings)
        
        accounts_file = "accounts.txt"
        
        if not os.path.exists(accounts_file):
            print(f"❌ Arquivo {accounts_file} não encontrado!")
            print("💡 Crie um arquivo com formato:")
            print("username1:password1")
            print("username2:password2:proxy2")
            return
        
        with open(accounts_file, 'r') as f:
            lines = f.readlines()
        
        success_count = 0
        total_count = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split(':')
            if len(parts) < 2:
                print(f"❌ Linha inválida: {line}")
                continue
            
            username = parts[0].strip()
            password = parts[1].strip()
            proxy = parts[2].strip() if len(parts) > 2 else None
            
            total_count += 1
            print(f"Adicionando {username}... ", end="")
            
            if pool.add_account(username, password, proxy):
                print("✅")
                success_count += 1
            else:
                print("❌")
        
        print(f"\n📊 Resultado: {success_count}/{total_count} contas adicionadas")
        
    except Exception as e:
        print(f"❌ Erro: {e}")


if __name__ == "__main__":
    import os
    
    # Verificar se deve usar arquivo
    if len(sys.argv) > 1 and sys.argv[1] == "from-file":
        add_accounts_from_file()
    else:
        # Interface interativa
        manager = AccountManager()
        asyncio.run(manager.run())