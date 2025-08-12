# app/api/routes.py
"""
Endpoints da Instagram Collection API
Otimizados para integração com N8N
"""

import time
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse

from app.api.responses import (
    CollectionResponse, HealthResponse, PoolStatusResponse, 
    ErrorResponse, APIInfoResponse, AccountIn, AccountBatchIn, AccountOut, AccountsListResponse, OperationResult,convert_collection_result_to_response
)
from app.core.collection_service import CollectionService
from app.config import Settings
from app.utils.logging_config import get_app_logger

from fastapi.encoders import jsonable_encoder

from app.models import InstagramAccount

# Logger
logger = get_app_logger(__name__)

# Router
router = APIRouter()

# Instância global do CollectionService (será inicializada no main.py)
collection_service: Optional[CollectionService] = None


def get_collection_service() -> CollectionService:
    """
    Obtém instância do CollectionService
    
    Returns:
        CollectionService inicializado
        
    Raises:
        HTTPException: Se service não estiver inicializado
    """
    global collection_service
    if collection_service is None:
        raise HTTPException(
            status_code=503,
            detail="CollectionService não inicializado"
        )
    return collection_service


def init_collection_service(settings: Settings):
    """
    Inicializa o CollectionService global
    
    Args:
        settings: Configurações da aplicação
    """
    global collection_service
    collection_service = CollectionService(settings)
    logger.success("CollectionService inicializado para API")



# ===================== Accounts Management =====================

@router.get("/accounts", response_model=AccountsListResponse, summary="[Accounts] Listar contas")
async def list_accounts():
    """Lista todas as contas do pool com status resumido"""
    service = get_collection_service()
    pool = service.account_pool

    items: list[AccountOut] = []
    for acc in pool.accounts:
        try:
            # usar fallback de disponibilidade (o método pode lançar)
            try:
                available = bool(acc.is_available())
            except Exception:
                available = pool._is_account_available_fallback(acc)
            items.append(AccountOut(
                username=acc.username,
                status=str(acc.status.value if hasattr(acc.status, "value") else acc.status),
                health_score=float(acc.health_score),
                operations_today=int(acc.operations_today),
                last_used=acc.last_used,
                available=available
            ))
        except Exception:
            continue

    return AccountsListResponse(total=len(items), accounts=items)


@router.post("/accounts", response_model=OperationResult, summary="[Accounts] Adicionar conta")
async def add_account(body: AccountIn):
    """
    Adiciona **uma** conta ao pool.  
    **Atenção:** a senha **não** é logada nem retornada.
    """
    service = get_collection_service()
    pool = service.account_pool

    ok = pool.add_account(body.username.strip(), body.password, body.proxy)
    if ok:
        return OperationResult(success=True, message=f"Conta {body.username} adicionada.")
    else:
        return OperationResult(success=False, message=f"Falha ao adicionar {body.username}.")


@router.post("/accounts/batch", response_model=OperationResult, summary="[Accounts] Adicionar múltiplas contas")
async def add_accounts_batch(body: AccountBatchIn):
    """Adiciona várias contas de uma vez."""
    service = get_collection_service()
    pool = service.account_pool

    added, failed = [], []
    for acc in body.accounts:
        ok = pool.add_account(acc.username.strip(), acc.password, acc.proxy)
        (added if ok else failed).append(acc.username)

    return OperationResult(
        success=len(failed) == 0,
        message=f"Adicionadas: {len(added)} | Falharam: {len(failed)}",
        details={"added": added, "failed": failed}
    )


@router.delete("/accounts/{username}", response_model=OperationResult, summary="[Accounts] Remover conta")
async def remove_account(username: str = Path(..., description="Username para remover", example="usuario.teste")):
    service = get_collection_service()
    pool = service.account_pool

    ok = pool.remove_account(username.strip())
    if ok:
        return OperationResult(success=True, message=f"Conta {username} removida.")
    return OperationResult(success=False, message=f"Conta {username} não encontrada.")


@router.post("/accounts/health-check", response_model=OperationResult, summary="[Accounts] Health check")
async def accounts_health_check():
    """Executa health check no pool (reseta operações diárias, tira de cooldown quando possível, tenta recuperar contas)."""
    service = get_collection_service()
    pool = service.account_pool

    pool.health_check()
    status = pool.get_pool_status()
    return OperationResult(
        success=True,
        message="Health check concluído.",
        details=status
    )


@router.post("/accounts/test/{username}", response_model=OperationResult, summary="[Accounts] Testar conta específica")
async def test_account(username: str = Path(..., description="Username a testar", example="usuario.teste")):
    """
    Faz login na conta e tenta obter o `timeline_feed` para validar sessão/proxy.
    """
    service = get_collection_service()
    pool = service.account_pool

    # localizar
    account = next((a for a in pool.accounts if a.username == username), None)
    if not account:
        return OperationResult(success=False, message=f"Conta {username} não encontrada.")

    client = pool.get_client(account)
    if not client:
        return OperationResult(success=False, message=f"Não foi possível obter cliente para {username}.")

    try:
        client.get_timeline_feed()
        # sucesso: atualiza saúde e retorna
        account.update_health_score(True)
        return OperationResult(
            success=True,
            message=f"Conta {username} OK.",
            details={
                "health_score": account.health_score,
                "status": str(account.status.value if hasattr(account.status, "value") else account.status),
                "operations_today": account.operations_today
            }
        )
    except Exception as e:
        account.update_health_score(False)
        return OperationResult(success=False, message=f"Erro no teste: {e.__class__.__name__}: {e}")
    
    
@router.get("/", response_model=APIInfoResponse, summary="Informações da API")
async def get_api_info():
    """
    Retorna informações básicas da API
    
    Returns:
        Informações da API, versão e endpoints disponíveis
    """
    return APIInfoResponse(
        name="Instagram Collection API",
        version="1.0.0",
        description="API para coleta de stories e posts do Instagram das últimas 24h",
        endpoints={
            "collect": "POST /collect/{username} - Coleta mídias de um usuário",
            "health": "GET /health - Health check da API", 
            "pool_status": "GET /pool-status - Status do pool de contas",
            "docs": "GET /docs - Documentação interativa"
        },
        documentation="/docs"
    )


@router.get("/health", response_model=HealthResponse, summary="Health Check")
async def health_check():
    """
    Verifica a saúde da API e do pool de contas
    
    Returns:
        Status da API e informações do pool
    """
    try:
        service = get_collection_service()
        pool_status = service.get_pool_status()
        
        # Determinar status geral
        api_status = "healthy"
        if pool_status['available_accounts'] == 0:
            api_status = "degraded"
        elif pool_status['total_accounts'] == 0:
            api_status = "unhealthy"
        
        return HealthResponse(
            status=api_status,
            timestamp=datetime.now(),
            version="1.0.0",
            pool_status={
                "total_accounts": pool_status["total_accounts"],
                "available_accounts": pool_status["available_accounts"],
                "average_health_score": pool_status["average_health_score"]
            }
        )
        
    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Health check falhou: {str(e)}"
        )


@router.get("/pool-status", response_model=PoolStatusResponse, summary="Status do Pool")
async def get_pool_status():
    """
    Retorna status detalhado do pool de contas
    
    Returns:
        Informações completas sobre o pool de contas Instagram
    """
    try:
        service = get_collection_service()
        status = service.get_pool_status()
        
        return PoolStatusResponse(
            total_accounts=status["total_accounts"],
            available_accounts=status["available_accounts"], 
            status_breakdown=status["status_breakdown"],
            average_health_score=status["average_health_score"],
            total_operations_today=status["total_operations_today"],
            last_health_check=datetime.fromisoformat(status["last_health_check"])
        )
        
    except Exception as e:
        logger.error(f"Erro ao obter status do pool: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao obter status do pool: {str(e)}"
        )


@router.post("/collect/{username}", response_model=CollectionResponse, summary="Coletar Mídias")
async def collect_user_content(
    username: str = Path(..., description="Username do Instagram (sem @)", example="cristiano"),
    include_stories: bool = Query(True, description="Incluir stories das últimas 24h"),
    include_feed: bool = Query(True, description="Incluir posts do feed das últimas 24h"),
    max_feed_posts: int = Query(10, ge=1, le=50, description="Máximo de posts do feed (1-50)")
):
    """
    Coleta stories e posts do feed de um usuário do Instagram
    
    **Funcionalidades:**
    - Coleta stories das últimas 24 horas
    - Coleta posts do feed das últimas 24 horas 
    - Retorna dados binários em base64
    - Usa pool de contas com rotação automática
    - Rate limiting inteligente
    
    **Parâmetros:**
    - `username`: Nome de usuário do Instagram (sem @)
    - `include_stories`: Se deve incluir stories (default: true)
    - `include_feed`: Se deve incluir posts do feed (default: true)
    - `max_feed_posts`: Máximo de posts para coletar (1-50, default: 10)
    
    **Response:**
    - Dados binários das mídias em base64
    - Metadados ricos (data, likes, tipo, etc.)
    - Estatísticas da coleta
    - Informações da conta usada
    
    **Erros comuns:**
    - 400: Username inválido
    - 404: Usuário não encontrado
    - 403: Perfil privado  
    - 429: Rate limit atingido
    - 503: Nenhuma conta disponível
    """
    # Validar username
    if not username or not username.strip():
        raise HTTPException(
            status_code=400,
            detail="Username é obrigatório"
        )
    
    # Limpar username
    clean_username = username.strip().lower().lstrip('@')
    
    # Validar caracteres do username
    if not clean_username.replace('_', '').replace('.', '').isalnum():
        raise HTTPException(
            status_code=400,
            detail="Username contém caracteres inválidos"
        )
    
    logger.info(f"Iniciando coleta para @{clean_username}")
    
    # Verificar se há contas disponíveis
    try:
        service = get_collection_service()
        pool_status = service.get_pool_status()
        
        if pool_status['available_accounts'] == 0:
            logger.warning("Nenhuma conta disponível no pool")
            raise HTTPException(
                status_code=503,
                detail="Nenhuma conta disponível no pool. Tente novamente em alguns minutos."
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao verificar pool: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao verificar pool de contas"
        )
    
    # Executar coleta
    collection_start_time = time.time()
    
    try:
        result = await service.collect_user_content(
            username=clean_username,
            include_stories=include_stories,
            include_feed=include_feed,
            max_feed_posts=max_feed_posts
        )
        
        # Verificar resultado
        if not result['success']:
            error_msg = result.get('error', 'Erro desconhecido na coleta')
            logger.warning(f"Coleta falhou para @{clean_username}: {error_msg}")
            
            # Mapear erros para códigos HTTP apropriados
            if 'não encontrado' in error_msg.lower():
                status_code = 404
            elif 'privado' in error_msg.lower():
                status_code = 403
            elif 'rate limit' in error_msg.lower():
                status_code = 429
            elif 'nenhuma conta' in error_msg.lower():
                status_code = 503
            else:
                status_code = 422
            
            raise HTTPException(
                status_code=status_code,
                detail=error_msg
            )
        
        # Converter resultado para response model
        response = convert_collection_result_to_response(result, collection_start_time)
        
        logger.success(f"Coleta bem-sucedida para @{clean_username}: {response.statistics.total_files} arquivos")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro inesperado na coleta para @{clean_username}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno do servidor: {str(e)}"
        )


# Endpoint adicional para limpeza (útil para desenvolvimento)
@router.post("/cleanup", summary="Limpeza de Recursos", include_in_schema=False)
async def cleanup_resources():
    """
    Executa limpeza de recursos temporários
    
    **Nota:** Endpoint de desenvolvimento, não incluído na documentação pública
    """
    try:
        service = get_collection_service()
        service.cleanup()
        
        return {
            "success": True,
            "message": "Limpeza de recursos executada",
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"Erro na limpeza: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro na limpeza: {str(e)}"
        )


# Error handlers personalizados
async def http_exception_handler(request, exc: HTTPException):
    """Handler customizado para HTTPException"""
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(ErrorResponse(
            error=exc.detail,
            timestamp=datetime.now(),
            username=request.path_params.get('username')
        ))
    )


async def general_exception_handler(request, exc: Exception):
    """Handler customizado para exceções gerais"""
    logger.error(f"Erro não tratado: {exc}")
    
    return JSONResponse(
        status_code=500,
        content=jsonable_encoder(ErrorResponse(
            error="Erro interno do servidor",
            detail=str(exc),
            timestamp=datetime.now()
        ))
    )