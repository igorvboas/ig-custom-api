#!/usr/bin/env python3
"""
Instagram Collection API - Aplicação Principal
FastAPI application para coleta de mídias do Instagram
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager

from app.config import Settings
from app.utils.logging_config import setup_logging, get_app_logger
from app.core.collection_service import CollectionService


# Configurações globais
settings = Settings()
setup_logging(settings)
logger = get_app_logger(__name__)

# Serviço de coleta global
collection_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    global collection_service
    
    # Startup
    logger.success("🚀 Iniciando Instagram Collection API")
    collection_service = CollectionService(settings)
    
    # Verificar se há contas no pool
    pool_status = collection_service.get_pool_status()
    logger.info(f"📊 Pool inicializado: {pool_status['available_accounts']} contas disponíveis")
    
    if pool_status['total_accounts'] == 0:
        logger.warning("⚠️ Nenhuma conta no pool! Use scripts/account_manager.py para adicionar contas")
    
    yield
    
    # Shutdown
    logger.info("🛑 Finalizando aplicação...")
    if collection_service:
        collection_service.cleanup()


# Criar aplicação FastAPI
app = FastAPI(
    title="Instagram Collection API",
    description="API para coleta de stories e feed posts do Instagram",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Endpoint raiz - informações da API"""
    return {
        "message": "Instagram Collection API",
        "version": "1.0.0",
        "endpoints": {
            "collect": "POST /collect/{username}",
            "health": "GET /health",
            "pool-status": "GET /pool-status"
        }
    }


@app.get("/health")
async def health_check():
    """Health check da API"""
    pool_status = collection_service.get_pool_status()
    
    return {
        "status": "healthy",
        "timestamp": "2024-08-05T15:30:00Z",
        "pool": {
            "total_accounts": pool_status["total_accounts"],
            "available_accounts": pool_status["available_accounts"],
            "average_health": pool_status["average_health_score"]
        }
    }


@app.get("/pool-status")
async def get_pool_status():
    """Status detalhado do pool de contas"""
    return collection_service.get_pool_status()


@app.post("/collect/{username}")
async def collect_user_content(
    username: str,
    include_stories: bool = True,
    include_feed: bool = True,
    max_feed_posts: int = 10
):
    """
    Coleta conteúdo de um usuário do Instagram
    
    Args:
        username: Nome de usuário do Instagram (sem @)
        include_stories: Se deve incluir stories (default: True)
        include_feed: Se deve incluir posts do feed (default: True)
        max_feed_posts: Máximo de posts do feed (default: 10)
    
    Returns:
        JSON com mídias coletadas em formato binário
    """
    if not username or not username.strip():
        raise HTTPException(status_code=400, detail="Username é obrigatório")
    
    # Limpar username
    clean_username = username.strip().lstrip('@')
    
    logger.info(f"📱 Coleta solicitada para @{clean_username}")
    
    try:
        result = await collection_service.collect_user_content(
            username=clean_username,
            include_stories=include_stories,
            include_feed=include_feed,
            max_feed_posts=max_feed_posts
        )
        
        if not result["success"]:
            logger.warning(f"❌ Falha na coleta para @{clean_username}: {result.get('error')}")
            raise HTTPException(
                status_code=422, 
                detail=f"Erro na coleta: {result.get('error', 'Erro desconhecido')}"
            )
        
        logger.success(f"✅ Coleta bem-sucedida para @{clean_username}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro inesperado na coleta para @{clean_username}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro interno do servidor: {str(e)}"
        )


if __name__ == "__main__":
    print("🚀 Iniciando Instagram Collection API...")
    print(f"📊 Configurações carregadas de: {settings.__class__.__name__}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info"
    )