# app/core/collection_service.py
"""
Serviço de alto nível para coleta de mídias
Interface simplificada para uso na API
"""

import asyncio
import base64
from datetime import datetime
from typing import Dict, Any, Optional
from app.core.media_collector import MediaCollector
from app.core.account_pool import AccountPool
from app.config import Settings
from app.utils.logging_config import get_app_logger

logger = get_app_logger(__name__)


class CollectionService:
    """
    Serviço de coleta que gerencia MediaCollector e AccountPool
    Interface simplificada para a API
    """
    
    def __init__(self, settings: Settings):
        """
        Inicializa o serviço de coleta
        
        Args:
            settings: Configurações da aplicação
        """
        self.settings = settings
        self.account_pool = AccountPool(settings)
        self.media_collector = MediaCollector(self.account_pool, settings)
        
        logger.success("CollectionService inicializado")
    
    async def collect_user_content(self, username: str, 
                                 include_stories: bool = True,
                                 include_feed: bool = True,
                                 max_feed_posts: int = 10) -> Dict[str, Any]:
        """
        Coleta conteúdo de um usuário e retorna em formato otimizado para API
        
        Args:
            username: Nome de usuário do Instagram
            include_stories: Se deve incluir stories
            include_feed: Se deve incluir posts do feed
            max_feed_posts: Máximo de posts do feed
            
        Returns:
            Dicionário com dados prontos para resposta da API
        """
        logger.info(f"Iniciando coleta para @{username}")
        
        # Verificar se temos contas disponíveis
        try:
            # CORREÇÃO: Usar status ACTIVE diretamente
            available_accounts = []
            total_accounts = len(self.account_pool.accounts) if hasattr(self.account_pool, 'accounts') else 0
            logger.info(f"Total de contas no pool: {total_accounts}")

            for acc in self.account_pool.accounts:
                logger.info(f"Verificando conta {acc.username}: status={acc.status}")
                # Usar status ACTIVE em vez de is_available()
                if str(acc.status).lower() == 'active' or acc.status.value == 'active':
                    available_accounts.append(acc)
                    logger.info(f"Conta {acc.username} está disponível (ACTIVE)")

            available_count = len(available_accounts)
            logger.info(f"Contas ACTIVE encontradas: {available_count}")

            if available_count == 0:
                logger.error("Nenhuma conta disponível no pool")
                return self._create_error_response(
                    username, 
                    "Nenhuma conta disponível no pool",
                    error_code="NO_ACCOUNTS_AVAILABLE"
                )
        except Exception as e:
            logger.error(f"Erro ao verificar contas disponíveis: {e}")
            return self._create_error_response(
                username, 
                f"Erro ao verificar pool de contas: {str(e)}",
                error_code="POOL_CHECK_ERROR"
            )
        
        # Executar coleta com tratamento de erros robusto
        try:
            logger.info(f"Executando coleta para @{username} com {available_accounts} contas disponíveis")
            
            result = await self.media_collector.collect_user_media(
                username=username,
                include_stories=include_stories,
                include_feed=include_feed,
                max_feed_posts=max_feed_posts
            )
            
            # Verificar se result é válido
            if result is None:
                logger.error("MediaCollector retornou None")
                return self._create_error_response(
                    username,
                    "Falha interna na coleta de dados",
                    error_code="NULL_RESULT"
                )
                
        except KeyError as e:
            logger.error(f"KeyError durante coleta: {e}")
            logger.error("Possível mudança na estrutura da API do Instagram")
            return self._create_error_response(
                username,
                f"Erro de estrutura de dados: {str(e)}. API do Instagram pode ter mudado.",
                error_code="DATA_STRUCTURE_ERROR"
            )
            
        except Exception as e:
            logger.error(f"Erro durante coleta: {type(e).__name__}: {e}")
            
            # Tratamento específico para erros conhecidos
            error_message = str(e).lower()
            if "login_required" in error_message:
                return self._create_error_response(
                    username,
                    "Todas as contas precisam de reautenticação",
                    error_code="LOGIN_REQUIRED"
                )
            elif "rate limit" in error_message or "too many requests" in error_message:
                return self._create_error_response(
                    username,
                    "Rate limit atingido. Tente novamente em alguns minutos",
                    error_code="RATE_LIMIT"
                )
            elif "user not found" in error_message or "doesn't exist" in error_message:
                return self._create_error_response(
                    username,
                    "Usuário não encontrado ou perfil privado",
                    error_code="USER_NOT_FOUND"
                )
            elif "validation error" in error_message or "pydantic" in error_message:
                return self._create_error_response(
                    username,
                    "Erro na estrutura de dados retornada pelo Instagram",
                    error_code="VALIDATION_ERROR"
                )
            elif "buffer has been detached" in error_message:
                return self._create_error_response(
                    username,
                    "Erro no processamento de dados binários",
                    error_code="BUFFER_ERROR"
                )
            else:
                return self._create_error_response(
                    username,
                    f"Erro interno: {str(e)}",
                    error_code="INTERNAL_ERROR"
                )
        
        # Verificar se a coleta foi bem-sucedida
        if not hasattr(result, 'success') or not result.success:
            error_msg = getattr(result, 'error_message', 'Erro desconhecido na coleta')
            logger.error(f"Coleta falhou: {error_msg}")
            return self._create_error_response(username, error_msg, error_code="COLLECTION_FAILED")
        
        # Converter para formato da API com tratamento seguro
        try:
            response_data = await self._build_success_response_safe(result, username)
            return response_data
            
        except Exception as e:
            logger.error(f"Erro ao construir resposta: {e}")
            return self._create_error_response(
                username,
                f"Erro ao processar dados coletados: {str(e)}",
                error_code="RESPONSE_BUILD_ERROR"
            )
    
    def _create_error_response(self, username: str, error_message: str, error_code: str = "UNKNOWN") -> Dict[str, Any]:
        """
        Cria resposta padronizada de erro
        
        Args:
            username: Nome do usuário
            error_message: Mensagem de erro
            error_code: Código do erro para debugging
            
        Returns:
            Dicionário de resposta de erro
        """
        return {
            "success": False,
            "error": error_message,
            "error_code": error_code,
            "username": username,
            "timestamp": datetime.now().isoformat(),
            "data": {
                "stories": [],
                "feed_posts": []
            },
            "statistics": {
                "total_files": 0,
                "total_size_mb": 0.0,
                "stories_count": 0,
                "feed_posts_count": 0
            }
        }
    
    async def _build_success_response_safe(self, result, username: str) -> Dict[str, Any]:
        """
        Constrói resposta de sucesso de forma segura para evitar erros Pydantic e buffer
        
        Args:
            result: Resultado da coleta do MediaCollector
            username: Nome do usuário
            
        Returns:
            Dicionário de resposta de sucesso
        """
        response_data = {
            "success": True,
            "username": username,
            "timestamp": getattr(result, 'timestamp', datetime.now()).isoformat(),
            "account_used": getattr(result, 'account_used', 'unknown'),
            "data": {
                "stories": [],
                "feed_posts": []
            }
        }
        
        # Converter stories para formato da API com tratamento ultra-seguro
        stories = getattr(result, 'stories', []) or []
        for i, story in enumerate(stories):
            try:
                story_data = self._convert_media_item_safe(story, 'story', i)
                if story_data:
                    response_data["data"]["stories"].append(story_data)
            except Exception as e:
                logger.warning(f"Erro ao processar story {i}: {e}")
                continue
        
        # Converter feed posts para formato da API com tratamento ultra-seguro
        feed_posts = getattr(result, 'feed_posts', []) or []
        for i, post in enumerate(feed_posts):
            try:
                post_data = self._convert_media_item_safe(post, 'feed_post', i)
                if post_data:
                    response_data["data"]["feed_posts"].append(post_data)
            except Exception as e:
                logger.warning(f"Erro ao processar post {i}: {e}")
                continue
        
        # Calcular estatísticas
        response_data["statistics"] = self._calculate_statistics_safe(response_data["data"])
        
        total_files = response_data["statistics"]["total_files"]
        total_size_mb = response_data["statistics"]["total_size_mb"]
        
        logger.success(f"Coleta concluída: {total_files} arquivos ({total_size_mb:.1f}MB)")
        
        return response_data
    
    def _convert_media_item_safe(self, media_item, item_type: str, index: int = 0) -> Optional[Dict[str, Any]]:
        """
        Converte um item de mídia para o formato da API de forma ultra-segura
        
        Args:
            media_item: Item de mídia do resultado
            item_type: Tipo do item ('story' ou 'feed_post')
            index: Índice do item para fallback
            
        Returns:
            Dicionário com dados do item ou None se inválido
        """
        try:
            # Obter ID de forma segura
            item_id = self._get_safe_attribute(media_item, 'id', f'unknown_{item_type}_{index}')
            
            # Obter binary_data de forma segura
            binary_data = self._get_safe_binary_data(media_item)
            
            # Converter binary data para base64 se necessário
            if isinstance(binary_data, bytes):
                try:
                    # Teste se o buffer está válido
                    _ = len(binary_data)
                    binary_data_b64 = base64.b64encode(binary_data).decode('utf-8')
                except (ValueError, TypeError) as e:
                    logger.warning(f"Erro ao converter binary data para base64: {e}")
                    binary_data_b64 = ""
                    binary_data = b''
            else:
                binary_data_b64 = ""
                binary_data = b''
            
            # Obter outros atributos de forma segura
            filename = self._get_safe_attribute(media_item, 'filename', f'{item_type}_{index}.jpg')
            size_bytes = self._get_safe_attribute(media_item, 'size_bytes', len(binary_data) if binary_data else 0)
            media_type = self._get_safe_attribute(media_item, 'type', 'unknown')
            
            # Construir metadata de forma segura
            metadata = self._build_safe_metadata(media_item, item_type)
            
            return {
                "id": str(item_id),
                "type": str(media_type),
                "filename": str(filename),
                "size_bytes": int(size_bytes) if isinstance(size_bytes, (int, float)) else 0,
                "binary_data": binary_data_b64,  # Base64 encoded para JSON
                "binary_data_raw": len(binary_data) > 0,  # Flag se há dados
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Erro ao converter {item_type} {index}: {e}")
            return None
    
    def _get_safe_attribute(self, obj, attr_name: str, default_value: Any = None) -> Any:
        """
        Obtém atributo de forma segura
        
        Args:
            obj: Objeto
            attr_name: Nome do atributo
            default_value: Valor padrão
            
        Returns:
            Valor do atributo ou padrão
        """
        try:
            if hasattr(obj, attr_name):
                value = getattr(obj, attr_name)
                return value if value is not None else default_value
            else:
                return default_value
        except Exception:
            return default_value
    
    def _get_safe_binary_data(self, media_item) -> bytes:
        """
        Obtém binary data de forma segura
        
        Args:
            media_item: Item de mídia
            
        Returns:
            Dados binários ou bytes vazios
        """
        try:
            binary_data = getattr(media_item, 'binary_data', b'')
            if isinstance(binary_data, bytes):
                # Testar se o buffer está válido
                _ = len(binary_data)
                return binary_data
            else:
                return b''
        except (ValueError, TypeError, AttributeError):
            logger.warning("Binary data inválido ou buffer detached")
            return b''
    
    def _build_safe_metadata(self, media_item, item_type: str) -> Dict[str, Any]:
        """
        Constrói metadata de forma segura
        
        Args:
            media_item: Item de mídia
            item_type: Tipo do item
            
        Returns:
            Dicionário com metadata
        """
        metadata = {
            "item_type": item_type,
            "processed_at": datetime.now().isoformat()
        }
        
        # Lista de atributos seguros para incluir
        safe_attributes = [
            'story_id', 'post_id', 'taken_at', 'media_type', 
            'username', 'is_story', 'like_count', 'comment_count',
            'hours_old', 'is_recent', 'duration_seconds', 'caption',
            'carousel_index', 'carousel_total', 'is_carousel'
        ]
        
        for attr in safe_attributes:
            try:
                value = getattr(media_item, 'metadata', {}).get(attr) if hasattr(media_item, 'metadata') else None
                if value is not None:
                    # Converter para tipos JSON-safe
                    if isinstance(value, datetime):
                        metadata[attr] = value.isoformat()
                    elif isinstance(value, (str, int, float, bool)):
                        metadata[attr] = value
                    elif isinstance(value, dict):
                        metadata[attr] = str(value)  # Converter dict para string para evitar erros
                    else:
                        metadata[attr] = str(value)
            except Exception:
                continue
        
        return metadata
    
    def _calculate_statistics_safe(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula estatísticas de forma segura
        
        Args:
            data: Dados coletados com stories e feed_posts
            
        Returns:
            Dicionário com estatísticas
        """
        try:
            stories = data.get("stories", []) or []
            feed_posts = data.get("feed_posts", []) or []
            
            total_files = len(stories) + len(feed_posts)
            
            total_size_bytes = 0
            for item in stories + feed_posts:
                try:
                    size_bytes = item.get("size_bytes", 0)
                    if isinstance(size_bytes, (int, float)) and size_bytes > 0:
                        total_size_bytes += size_bytes
                except Exception:
                    continue
            
            total_size_mb = total_size_bytes / (1024 * 1024) if total_size_bytes > 0 else 0.0
            
            return {
                "total_files": total_files,
                "total_size_mb": round(total_size_mb, 2),
                "stories_count": len(stories),
                "feed_posts_count": len(feed_posts),
                "total_size_bytes": total_size_bytes
            }
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            return {
                "total_files": 0,
                "total_size_mb": 0.0,
                "stories_count": 0,
                "feed_posts_count": 0,
                "total_size_bytes": 0
            }
    
    def get_pool_status(self) -> Dict[str, Any]:
        """
        Retorna status do pool de contas
        
        Returns:
            Status detalhado do pool
        """
        try:
            return self.account_pool.get_pool_status()
        except Exception as e:
            logger.error(f"Erro ao obter status do pool: {e}")
            return {
                "error": f"Erro ao obter status: {str(e)}",
                "total_accounts": 0,
                "available_accounts": 0,
                "healthy_accounts": 0
            }
    
    def cleanup(self):
        """
        Executa limpeza de recursos
        """
        try:
            self.media_collector.cleanup_temp_files()
            logger.info("Limpeza de recursos concluída")
        except Exception as e:
            logger.error(f"Erro durante limpeza: {e}")