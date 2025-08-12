# app/core/media_collector.py
"""
Sistema de coleta de mídias do Instagram (Stories + Feed)
Otimizado para performance e compatibilidade com N8N
"""

import os
import asyncio
import time
import random
import tempfile
import hashlib
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import mimetypes
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone


from instagrapi import Client
from instagrapi.types import Story, Media, User
from instagrapi.exceptions import (
    UserNotFound, PrivateError, LoginRequired, 
    ChallengeRequired, RateLimitError, MediaNotFound,
    ClientError, PleaseWaitFewMinutes
)

from app.config import Settings
from app.models import InstagramAccount, MediaFile, CollectionResult, MediaType, AccountStatus
from app.core.account_pool import AccountPool
from app.utils.logging_config import get_app_logger

# topo do arquivo:
import requests

# ADD no topo do arquivo (imports)
from pydantic import ValidationError as PydValidationError
try:
    from pydantic_core._pydantic_core import ValidationError as CoreValidationError  # pydantic v2
except Exception:
    CoreValidationError = Exception

logger = get_app_logger(__name__)


class MediaCollector:
    """
    Coletor de mídias do Instagram com otimizações para API
    """
    
    def __init__(self, account_pool: AccountPool, settings: Settings):
        """
        Inicializa o coletor de mídias
        
        Args:
            account_pool: Pool de contas Instagram
            settings: Configurações da aplicação
        """
        self.pool = account_pool
        self.settings = settings
        self.executor = ThreadPoolExecutor(max_workers=2)  # Para operações síncronas
        
        # Garantir path absoluto para temp_downloads
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        self.temp_dir = project_root / "data" / "temp_downloads"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"MediaCollector inicializado - temp_dir: {self.temp_dir}")
    
    async def collect_user_media(self, username: str, include_stories: bool = True, 
                                include_feed: bool = True, max_feed_posts: int = 10) -> CollectionResult:
        """
        Coleta mídias de um usuário (stories + feed posts)
        
        Args:
            username: Nome de usuário do Instagram
            include_stories: Se deve incluir stories
            include_feed: Se deve incluir posts do feed
            max_feed_posts: Máximo de posts do feed para coletar
            
        Returns:
            CollectionResult com mídias coletadas
        """
        feed_posts = []
        feed_files = []

        start_time = time.time()
        logger.info(f"Iniciando coleta para @{username}")
        
        # Validar entrada
        if not username or not isinstance(username, str):
            error_msg = "Nome de usuário inválido"
            logger.error(error_msg)
            return CollectionResult(
                username=username,
                success=False,
                error_message=error_msg
            )
        
        # Obter conta disponível
        account = self.pool.get_available_account()
        if not account:
            error_msg = "Nenhuma conta disponível no pool"
            logger.error(error_msg)
            return CollectionResult(
                username=username,
                success=False,
                error_message=error_msg
            )
        
        # Obter cliente configurado
        client = self.pool.get_client(account)
        if not client:
            error_msg = f"Não foi possível obter cliente para {account.username}"
            logger.error(error_msg)
            return CollectionResult(
                username=username,
                success=False,
                error_message=error_msg
            )
        
        result = CollectionResult(username=username, account_used=account.username)
        
        try:
            # Obter informações do usuário target
            try:
                target_user = await self._get_user_info_safe(client, username)
                if not target_user:
                    raise UserNotFound(f"Usuário {username} não encontrado")
                    
                logger.info(f"Usuário encontrado: @{username} (ID: {target_user.pk})")
                
            except UserNotFound as e:
                error_msg = f"Usuário {username} não encontrado ou perfil privado"
                logger.warning(error_msg)
                self.pool.mark_account_used(account, success=True)  # Não é erro da conta
                result.success = False
                result.error_message = error_msg
                return result
                
            except Exception as e:
                error_msg = f"Erro ao buscar usuário {username}: {str(e)}"
                logger.error(error_msg)
                self.pool.mark_account_used(account, success=False)
                result.success = False
                result.error_message = error_msg
                return result
            
            # Adicionar delay entre operações
            await self._random_delay()
            
            # Coletar stories se solicitado
            if include_stories:
                logger.info(f"Coletando stories de @{username}")
                try:
                    stories = await self._collect_stories_safe(client, target_user.pk)
                    if stories:
                        logger.success(f"Encontrados {len(stories)} stories")
                        
                        # Download dos stories
                        story_files = await self._download_stories_safe(client, stories, username)
                        result.stories = story_files
                        
                        logger.success(f"Downloaded {len(story_files)} story files")
                    else:
                        logger.info(f"Nenhum story encontrado para @{username}")
                        
                except Exception as e:
                    logger.warning(f"Erro ao coletar stories: {str(e)}")
                    # Não falha a operação inteira por erro nos stories
            
            # Adicionar delay entre stories e feed
            await self._random_delay()
            
            # Coletar feed posts se solicitado
           
            if include_feed:
                logger.info(f"Coletando posts das últimas 24h de @{username} (max: {max_feed_posts})")
                try:
                    feed_posts = await self._collect_feed_posts_safe(client, target_user.pk, max_feed_posts)
                    logger.success(f"Encontrados {len(feed_posts)} posts das últimas 24h")
                    if feed_posts:
                        feed_files = await self._download_feed_posts_safe(client, feed_posts, username)
                        result.feed_posts = feed_files
                        logger.success(f"Downloaded {len(feed_files)} feed files das últimas 24h")
                    else:
                        logger.info(f"Nenhum post das últimas 24h encontrado para @{username}")
                except Exception as e:
                    logger.warning(f"Erro ao coletar feed: {str(e)}")


            
            # Marcar conta como usada com sucesso
            self.pool.mark_account_used(account, success=True)
            
            # Estatísticas finais
            total_files = len(result.stories) + len(result.feed_posts)
            total_time = time.time() - start_time
            
            logger.success(f"Coleta concluída para @{username}: {total_files} arquivos em {total_time:.1f}s")
            
            result.success = True
            return result
            
        except PrivateError:
            error_msg = f"Perfil @{username} é privado"
            logger.warning(error_msg)
            self.pool.mark_account_used(account, success=True)  # Não é erro da conta
            result.success = False
            result.error_message = error_msg
            return result
            
        except (RateLimitError, PleaseWaitFewMinutes):
            error_msg = f"Rate limit atingido para {account.username}"
            logger.warning(error_msg)
            account.status = AccountStatus.COOLDOWN
            self.pool.mark_account_used(account, success=False)
            result.success = False
            result.error_message = error_msg
            return result
            
        except LoginRequired:
            error_msg = f"Login requerido para conta {account.username}"
            logger.error(error_msg)
            account.status = AccountStatus.ERROR
            self.pool.mark_account_used(account, success=False)
            result.success = False
            result.error_message = error_msg
            return result
            
        except Exception as e:
            error_msg = f"Erro inesperado na coleta: {type(e).__name__}: {str(e)}"
            logger.error(error_msg)
            self.pool.mark_account_used(account, success=False)
            result.success = False
            result.error_message = error_msg
            return result
    
    async def _get_user_info_safe(self, client: Client, username: str) -> Optional[User]:
        """
        Obtém informações do usuário de forma segura usando ThreadPoolExecutor
        
        Args:
            client: Cliente Instagram
            username: Nome de usuário
            
        Returns:
            User object ou None se não encontrado
        """
        def _get_user_sync():
            try:
                # Tentar método principal
                user = client.user_info_by_username(username)
                return user, None
            except Exception as e:
                logger.warning(f"Método principal falhou, tentando alternativo: {e}")
                try:
                    user_id = client.user_id_from_username(username)
                    user = client.user_info(user_id)
                    return user, None
                except Exception as e2:
                    logger.error(f"Ambos os métodos falharam: {e2}")
                    return None, str(e2)
        
        try:
            await self._random_delay(0.5, 1.5)
            user, error = await asyncio.get_event_loop().run_in_executor(
                self.executor, _get_user_sync
            )
            
            if error and "not found" in error.lower():
                raise UserNotFound(error)
            elif error:
                raise Exception(error)
                
            return user
            
        except Exception as e:
            logger.error(f"Erro ao obter informações do usuário {username}: {e}")
            raise
    
    async def _collect_stories_safe(self, client: Client, user_id: int) -> List[Story]:
        """
        Coleta stories de um usuário de forma segura
        
        Args:
            client: Cliente Instagram
            user_id: ID do usuário
            
        Returns:
            Lista de stories
        """
        def _get_stories_sync():
            try:
                stories = client.user_stories(user_id)
                return stories or [], None
            except Exception as e:
                return [], str(e)
        
        try:
            await self._random_delay()
            stories, error = await asyncio.get_event_loop().run_in_executor(
                self.executor, _get_stories_sync
            )
            
            if error:
                if "login_required" in error.lower():
                    raise LoginRequired(error)
                else:
                    logger.warning(f"Erro ao coletar stories: {error}")
                    return []
            
            return stories
            
        except Exception as e:
            logger.warning(f"Erro ao coletar stories: {e}")
            return []
    


    async def _collect_feed_posts_safe(self, client: Client, user_id: int, max_posts: int) -> List[Media]:
        """
        Coleta posts (inclui Reels) das últimas 24h com fallbacks tolerantes:
        GQL -> V1 -> CLIPS -> RAW (private_request sem pydantic)
        """
        def _normalize_dt(dt):
            if not dt:
                return None
            try:
                if getattr(dt, "tzinfo", None) is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                return None

        def _safe_list(medias):
            safe = []
            for m in medias or []:
                try:
                    _ = getattr(m, "pk", None)
                    _ = getattr(m, "taken_at", None)
                    safe.append(m)
                except (PydValidationError, CoreValidationError, AttributeError, TypeError):
                    continue
            return safe

        def _get_feed_gql():
            medias = client.user_medias_gql(user_id, amount=min(max_posts * 5, 50))
            return _safe_list(medias)

        def _get_feed_v1():
            medias = client.user_medias_v1(user_id, amount=min(max_posts * 5, 50))
            return _safe_list(medias)

        def _get_clips():
            medias = client.user_clips(user_id, amount=min(max_posts * 5, 50))
            return _safe_list(medias)

        # Fallback RAW: não usa pydantic; montamos stubs simples
        def _get_feed_raw():
            try:
                # endpoint privado v1
                resp = client.private_request(
                    f"feed/user/{user_id}/",
                    params={"count": min(max_posts * 5, 50)}
                )
                items = resp.get("items", []) or []
            except Exception as e:
                logger.warning(f"RAW feed falhou: {e}")
                return []

            class _Stub:
                __slots__ = ("pk", "media_type", "taken_at", "resources", "is_pinned")
                def __init__(self, pk, media_type, taken_at, resources=None, is_pinned=False):
                    self.pk = pk
                    self.media_type = media_type
                    self.taken_at = taken_at
                    self.resources = resources or []
                    self.is_pinned = is_pinned

            stubs = []
            for it in items:
                try:
                    pk = it.get("pk") or it.get("id")
                    if not pk:
                        continue
                    media_type = it.get("media_type")  # 1 img, 2 video, 8 carousel
                    ts = it.get("taken_at") or it.get("device_timestamp")
                    # ts geralmente é epoch seconds
                    taken_at = datetime.fromtimestamp(ts, tz=timezone.utc) if isinstance(ts, (int, float)) else None

                    # carousel recursos (se quisermos baixar cada node depois)
                    resources = []
                    if media_type == 8:
                        for r in it.get("carousel_media", []) or []:
                            r_pk = r.get("pk") or r.get("id")
                            r_type = r.get("media_type")
                            resources.append(type("R", (), {"pk": r_pk, "media_type": r_type}))

                    is_pinned = bool(it.get("is_pinned", False))
                    stubs.append(_Stub(str(pk), int(media_type) if media_type else None, taken_at, resources, is_pinned))
                except Exception:
                    continue
            return stubs

        try:
            await self._random_delay()

            all_medias: List[Media] = []
            try:
                all_medias = _get_feed_gql()
            except Exception as e1:
                logger.warning(f"GQL falhou, tentando V1: {e1}")
                try:
                    all_medias = _get_feed_v1()
                except Exception as e2:
                    logger.warning(f"V1 falhou, tentando CLIPS: {e2}")
                    try:
                        all_medias = _get_clips()
                    except Exception as e3:
                        logger.warning(f"CLIPS também falhou, usando RAW: {e3}")
                        all_medias = _get_feed_raw()

            if not all_medias:
                return []

            twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
            recent = []
            for media in all_medias:
                if getattr(media, "is_pinned", False):
                    continue
                taken_at = _normalize_dt(getattr(media, "taken_at", None))
                if not taken_at:
                    continue
                if taken_at >= twenty_four_hours_ago:
                    recent.append(media)
                    if len(recent) >= max_posts:
                        break
                else:
                    break

            logger.info(f"Posts filtrados: {len(recent)} dos últimos {len(all_medias)} são das últimas 24h")
            return recent

        except (PydValidationError, CoreValidationError) as e:
            logger.warning(f"Validação de mídia quebrou, retornando vazio: {e}")
            return []
        except Exception as e:
            logger.warning(f"Erro ao coletar feed posts: {e}")
            return []



    
    async def _download_stories_safe(self, client: Client, stories: List[Story], username: str) -> List[MediaFile]:
        """
        Baixa arquivos dos stories de forma segura
        
        Args:
            client: Cliente Instagram
            stories: Lista de stories
            username: Nome do usuário (para organização)
            
        Returns:
            Lista de MediaFile com dados binários
        """
        media_files = []
        
        for i, story in enumerate(stories, 1):
            try:
                logger.info(f"Baixando story {i}/{len(stories)}")
                
                # Delay entre downloads
                if i > 1:
                    await self._random_delay(1.0, 2.0)
                
                media_file = await self._download_story_file_safe(client, story, username)
                if media_file:
                    media_files.append(media_file)
                    
            except Exception as e:
                if "login_required" in str(e).lower():
                    logger.error(f"Login requerido ao baixar story {story.pk}: {e}")
                    raise LoginRequired(str(e))
                else:
                    logger.warning(f"Erro ao baixar story {story.pk}: {e}")
                    continue
        
        return media_files
    
    async def _download_feed_posts_safe(self, client: Client, posts: List[Media], username: str) -> List[MediaFile]:
        """
        Baixa arquivos dos posts do feed de forma segura
        
        Args:
            client: Cliente Instagram
            posts: Lista de posts
            username: Nome do usuário (para organização)
            
        Returns:
            Lista de MediaFile com dados binários
        """
        media_files = []
        
        for i, post in enumerate(posts, 1):
            try:
                logger.info(f"Baixando post {i}/{len(posts)}")
                
                # Delay entre downloads
                if i > 1:
                    await self._random_delay(1.0, 2.0)
                
                # Posts podem ter múltiplas mídias (carrossel)
                if post.media_type == 8:  # Carrossel
                    carousel_files = await self._download_carousel_post_safe(client, post, username)
                    media_files.extend(carousel_files)
                else:
                    # Post simples (foto ou vídeo)
                    media_file = await self._download_single_post_safe(client, post, username)
                    if media_file:
                        media_files.append(media_file)
                        
            except Exception as e:
                if "login_required" in str(e).lower():
                    logger.error(f"Login requerido ao baixar post {post.pk}: {e}")
                    raise LoginRequired(str(e))
                else:
                    logger.warning(f"Erro ao baixar post {post.pk}: {e}")
                    continue
        
        return media_files
    
    async def _download_story_file_safe(self, client: Client, story: Story, username: str) -> Optional[MediaFile]:
        """
        Baixa arquivo individual de story de forma segura
        
        Args:
            client: Cliente Instagram
            story: Story object
            username: Nome do usuário
            
        Returns:
            MediaFile com dados binários ou None se erro
        """
        def _download_story_sync():
            try:
                temp_file = None
                media_type = None
                
                if story.media_type == 1:  # Foto
                    temp_file = client.photo_download(story.pk, folder=str(self.temp_dir))
                    media_type = MediaType.IMAGE
                elif story.media_type == 2:  # Vídeo
                    temp_file = client.video_download(story.pk, folder=str(self.temp_dir))
                    media_type = MediaType.VIDEO
                else:
                    return None, f"Tipo de story não suportado: {story.media_type}", None
                
                if not temp_file or not os.path.exists(temp_file):
                    return None, f"Arquivo não baixado: {story.pk}", None
                
                return temp_file, None, media_type
                
            except Exception as e:
                return None, str(e), None
        
        try:
            temp_file, error, media_type = await asyncio.get_event_loop().run_in_executor(
                self.executor, _download_story_sync
            )
            
            if error:
                if "login_required" in error.lower():
                    raise LoginRequired(error)
                else:
                    logger.warning(f"Erro no download do story: {error}")
                    return None
            
            if not temp_file:
                return None
            
            # Ler dados binários
            try:
                with open(temp_file, 'rb') as f:
                    binary_data = f.read()
                
                # Remover arquivo temporário
                os.remove(temp_file)
                
                # Criar MediaFile
                filename = f"story_{story.pk}_{username}.{self._get_file_extension(media_type)}"
                
                metadata = {
                    "story_id": story.pk,
                    "taken_at": story.taken_at.isoformat() if story.taken_at else None,
                    "media_type": story.media_type,
                    "username": username,
                    "is_story": True
                }
                
                # Adicionar metadados específicos se disponíveis
                if hasattr(story, 'video_duration') and story.video_duration:
                    metadata["duration_seconds"] = story.video_duration
                    
                if hasattr(story, 'caption_text') and story.caption_text:
                    metadata["caption"] = story.caption_text
                
                media_file = MediaFile(
                    id=story.pk,
                    type=media_type,
                    binary_data=binary_data,
                    filename=filename,
                    size_bytes=len(binary_data),
                    metadata=metadata
                )
                
                return media_file
                
            except Exception as e:
                logger.error(f"Erro ao processar arquivo baixado {temp_file}: {e}")
                # Tentar remover arquivo mesmo em caso de erro
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
                return None
            
        except Exception as e:
            logger.error(f"Erro ao baixar story {story.pk}: {e}")
            return None
    


    def _best_media_urls(self, post):
        """
        Retorna uma lista de (media_type, url) para o post (inclui carrossel).
        media_type: 1=imagem, 2=vídeo
        """
        urls = []
        try:
            if getattr(post, "media_type", None) == 8 and getattr(post, "resources", None):
                # carrossel
                for r in post.resources:
                    if getattr(r, "media_type", None) == 2:
                        url = getattr(r, "video_url", None) or getattr(r, "thumbnail_url", None)
                        if url: urls.append((2, url))
                    else:
                        url = getattr(r, "thumbnail_url", None)
                        if url: urls.append((1, url))
            else:
                # post simples
                if getattr(post, "media_type", None) == 2:
                    url = getattr(post, "video_url", None) or getattr(post, "thumbnail_url", None)
                    if url: urls.append((2, url))
                else:
                    url = getattr(post, "thumbnail_url", None)
                    if url: urls.append((1, url))
        except Exception:
            pass
        return urls

    def _fetch_url_bytes(self, url: str) -> Optional[bytes]:
        try:
            # sem cookies e sem headers especiais: CDN pública
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            logger.warning(f"Falha ao baixar URL direta: {e}")
        return None





    async def _download_single_post_safe(self, client: Client, post: Media, username: str) -> Optional[MediaFile]:
        pairs = self._best_media_urls(post)
        if not pairs:
            logger.warning(f"Nenhuma URL pública para post {getattr(post, 'pk', '???')}")
            return None

        # pega a primeira url “melhor”
        media_type_num, url = pairs[0]
        binary_data = await asyncio.get_event_loop().run_in_executor(self.executor, self._fetch_url_bytes, url)
        if not binary_data:
            return None

        mtype = MediaType.VIDEO if media_type_num == 2 else MediaType.IMAGE
        filename = f"post_{post.pk}_{username}.{self._get_file_extension(mtype)}"

        metadata={
            # "post_id": getattr(post, "pk", None),
            "post_id": str(getattr(post, "pk", "")),
            "taken_at": post.taken_at.isoformat() if getattr(post, "taken_at", None) else None,
            "media_type": getattr(post, "media_type", None),
            "username": username,
            "is_story": False,
            "like_count": getattr(post, "like_count", 0),
            "comment_count": getattr(post, "comment_count", 0),
            **({"hours_old": round((datetime.now(timezone.utc) - post.taken_at).total_seconds()/3600, 1),
                "is_recent": (datetime.now(timezone.utc) - post.taken_at).total_seconds() <= 24*3600}
               if getattr(post, "taken_at", None) else {})
        }
        if getattr(post, "taken_at", None):
            hours_old = (datetime.now(timezone.utc) - post.taken_at).total_seconds() / 3600
            metadata["hours_old"] = round(hours_old, 1)
            metadata["is_recent"] = hours_old <= 24
        if getattr(post, "video_duration", None):
            metadata["duration_seconds"] = post.video_duration
        if getattr(post, "caption_text", None):
            metadata["caption"] = post.caption_text[:500]

        return MediaFile(
            # id=getattr(post, "pk", None),
            id=str(getattr(post, "pk", "")),
            type=mtype,
            binary_data=binary_data,
            filename=filename,
            size_bytes=len(binary_data),
            metadata=metadata
        )

    
    async def _download_carousel_post_safe(self, client: Client, post: Media, username: str) -> List[MediaFile]:
        media_files = []
        pairs = self._best_media_urls(post)
        if not pairs:
            return media_files

        for i, (media_type_num, url) in enumerate(pairs, 1):
            binary_data = await asyncio.get_event_loop().run_in_executor(self.executor, self._fetch_url_bytes, url)
            if not binary_data:
                continue

            mtype = MediaType.VIDEO if media_type_num == 2 else MediaType.IMAGE
            filename = f"carousel_{post.pk}_{i}_{username}.{self._get_file_extension(mtype)}"
            metadata = {
                # "post_id": getattr(post, "pk", None),
                "post_id": str(getattr(post, "pk", "")),
                "carousel_index": i,
                "carousel_total": len(pairs),
                "taken_at": post.taken_at.isoformat() if getattr(post, "taken_at", None) else None,
                "media_type": media_type_num,
                "username": username,
                "is_story": False,
                "is_carousel": True
            }
            media_files.append(MediaFile(
                # id=f"{getattr(post, 'pk', 'unknown')}_{i}",
                id=f"{str(getattr(post, 'pk', 'unknown'))}_{i}",
                type=mtype,
                binary_data=binary_data,
                filename=filename,
                size_bytes=len(binary_data),
                metadata=metadata
            ))

            if i < len(pairs):
                await self._random_delay(0.5, 1.0)

        return media_files

    
    def _get_file_extension(self, media_type: MediaType) -> str:
        """
        Retorna extensão de arquivo baseada no tipo de mídia
        
        Args:
            media_type: Tipo da mídia
            
        Returns:
            Extensão do arquivo
        """
        extensions = {
            MediaType.IMAGE: "jpg",
            MediaType.VIDEO: "mp4",
            MediaType.CAROUSEL: "jpg"  # Default para carrossel
        }
        return extensions.get(media_type, "bin")
    
    async def _random_delay(self, min_delay: float = None, max_delay: float = None):
        """
        Adiciona delay aleatório para simular comportamento humano
        
        Args:
            min_delay: Delay mínimo (usa configuração se None)
            max_delay: Delay máximo (usa configuração se None)
        """
        min_d = min_delay or self.settings.request_delay_min
        max_d = max_delay or self.settings.request_delay_max
        
        delay = random.uniform(min_d, max_d)
        await asyncio.sleep(delay)
    
    def cleanup_temp_files(self):
        """
        Limpa arquivos temporários antigos
        """
        try:
            now = time.time()
            cutoff = now - (3600)  # 1 hora
            
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    
            logger.info("Limpeza de arquivos temporários concluída")
            
        except Exception as e:
            logger.warning(f"Erro na limpeza de arquivos temporários: {e}")
    
    def __del__(self):
        """Limpa o ThreadPoolExecutor quando o objeto é destruído"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)