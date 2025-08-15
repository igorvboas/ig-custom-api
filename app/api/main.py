# app/main.py
"""
Instagram Collection API - Aplicação Principal FastAPI
API REST para coleta de mídias do Instagram otimizada para N8N
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
from datetime import datetime

from app.config import Settings
from app.utils.logging_config import setup_logging, get_app_logger
from app.api.routes import router, init_collection_service, http_exception_handler, general_exception_handler
from app.api.responses import ErrorResponse

from app.api import onboarding as onboarding_ui  # <-- ADICIONE

# Configurações globais
settings = Settings()
setup_logging(settings)
logger = get_app_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia ciclo de vida da aplicação FastAPI
    
    Startup:
    - Inicializa CollectionService
    - Verifica pool de contas
    - Configura logs
    
    Shutdown:
    - Executa limpeza de recursos
    """
    # === STARTUP ===
    logger.success("🚀 Iniciando Instagram Collection API")
    
    try:
        # Inicializar CollectionService
        init_collection_service(settings)
        logger.success("✅ CollectionService inicializado")
        
        # Verificar pool de contas
        from app.api.routes import get_collection_service
        service = get_collection_service()
        pool_status = service.get_pool_status()
        
        logger.info(f"📊 Pool inicializado: {pool_status['total_accounts']} contas, {pool_status['available_accounts']} disponíveis")
        
        if pool_status['total_accounts'] == 0:
            logger.warning("⚠️ AVISO: Nenhuma conta no pool! Adicione contas com: python manage_accounts.py")
        elif pool_status['available_accounts'] == 0:
            logger.warning("⚠️ AVISO: Nenhuma conta disponível (todas em cooldown)")
        else:
            logger.success(f"✅ {pool_status['available_accounts']} contas prontas para uso")
        
        # Log de configurações importantes
        logger.info(f"⚙️ Configurações:")
        logger.info(f"   📁 Sessions: {settings.session_dir}")
        logger.info(f"   📁 Downloads: {settings.downloads_dir}")
        logger.info(f"   ⏱️ Cooldown: {settings.account_cooldown_minutes} min")
        logger.info(f"   📊 Max accounts: {settings.max_accounts}")
        
    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {e}")
        raise
    
    logger.success("🎉 API inicializada com sucesso!")
    
    yield
    
    # === SHUTDOWN ===
    logger.info("🛑 Finalizando Instagram Collection API")
    
    try:
        # Executar limpeza
        service = get_collection_service()
        service.cleanup()
        logger.info("🧹 Limpeza de recursos concluída")
        
    except Exception as e:
        logger.warning(f"⚠️ Erro na limpeza: {e}")
    
    logger.info("👋 API finalizada")


# Criar aplicação FastAPI
app = FastAPI(
    title="Instagram Collection API",
    description="""
## 📱 API para Coleta de Mídias do Instagram

API REST otimizada para coleta automatizada de stories e posts do Instagram, 
projetada especificamente para integração com N8N e processamento por IA.

### 🎯 Características Principais

- ✅ **Coleta stories** das últimas 24 horas
- ✅ **Coleta posts** do feed das últimas 24 horas  
- ✅ **Pool de contas** com rotação automática
- ✅ **Rate limiting** inteligente
- ✅ **Dados binários** em base64
- ✅ **Metadados ricos** para análise por IA
- ✅ **Health monitoring** em tempo real

### 🔄 Integração N8N

```javascript
// Exemplo de uso no N8N
const response = await this.helpers.httpRequest({
    method: 'POST',
    url: 'http://localhost:8000/collect/cristiano',
    json: true,
    body: {
        include_stories: true,
        include_feed: true,
        max_feed_posts: 10
    }
});

// Processar mídias retornadas
const stories = response.data.stories;
const posts = response.data.feed_posts;
```

### 📊 Dados Retornados

- **Stories**: Fotos e vídeos das últimas 24h
- **Feed Posts**: Posts das últimas 24h (imagens, vídeos, carrosséis)
- **Metadados**: Data, likes, comments, duração, caption, etc.
- **Binários**: Dados em base64 prontos para processamento

### 🛡️ Rate Limiting

A API usa um sistema inteligente de pool de contas para evitar bloqueios:
- Rotação automática entre contas
- Cooldown de 2h por conta
- Máximo de 100 operações/dia por conta
- Health monitoring contínuo

### 📈 Monitoramento

- `GET /health` - Status da API e pool
- `GET /pool-status` - Detalhes do pool de contas
- Logs detalhados para debugging
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configurar CORS para N8N
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5678",  # N8N default
        "http://localhost:3000",  # Development
        "http://127.0.0.1:5678",
        "http://127.0.0.1:3000",
        "*"  # Para desenvolvimento - restringir em produção
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Incluir routes
app.include_router(router, prefix="", tags=["Instagram Collection"])

# >>> ADICIONE O ROUTER DA UI <<<
app.include_router(onboarding_ui.router)

# Exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)


# Endpoint adicional de status na raiz
@app.get("/status", include_in_schema=False)
async def api_status():
    """Status rápido da API"""
    return {
        "api": "Instagram Collection API",
        "status": "running", 
        "timestamp": datetime.now(),
        "version": "1.0.0"
    }


# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request, call_next):
    """Log de todas as requests"""
    import time as _time
    start = _time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        # Mesmo se der erro, logamos o tempo decorrido
        elapsed_ms = (_time.perf_counter() - start) * 1000
        status = getattr(response, "status_code", "ERR")
        logger.info(f"📨 {request.method} {request.url.path} -> {status} ({elapsed_ms:.1f} ms)")
