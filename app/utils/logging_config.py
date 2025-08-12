# app/utils/logging_config.py
"""
Configuração de logging para a API
"""
import logging
import logging.handlers
import sys
from pathlib import Path

# Import corrigido
try:
    from app.config import Settings
except ImportError:
    # Fallback para execução direta
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from app.config import Settings


def setup_logging(settings: Settings):
    """
    Configura sistema de logging otimizado e limpo
    
    Args:
        settings: Configurações da aplicação
    """
    # Criar diretório de logs
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configurar formato
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler para arquivo com encoding UTF-8 (DETALHADO)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / settings.log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)  # Arquivo: INFO e acima
    
    # Handler para console SIMPLIFICADO (só coisas importantes)
    console_handler = logging.StreamHandler(sys.__stdout__)
    console_formatter = logging.Formatter(
        '%(levelname)s - %(message)s'  # Formato mais limpo para console
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.WARNING)  # Console: só WARNING e ERROR
    
    # No Windows, configurar encoding do console
    #if sys.platform == "win32":
    #    try:
    #        import codecs
    #        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    #    except:
    #        pass
    
    # Configurar logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Nível geral: INFO
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # SILENCIAR LOGS VERBOSOS - VERSÃO COMPLETA
    # Instagrapi - muito verboso, só erros
    logging.getLogger('instagrapi').setLevel(logging.ERROR)
    logging.getLogger('instagrapi.mixins').setLevel(logging.ERROR)
    logging.getLogger('instagrapi.mixins.private').setLevel(logging.ERROR)
    logging.getLogger('instagrapi.mixins.media').setLevel(logging.ERROR)
    logging.getLogger('instagrapi.mixins.user').setLevel(logging.ERROR)
    logging.getLogger('instagrapi.extractors').setLevel(logging.ERROR)
    logging.getLogger('private_request').setLevel(logging.ERROR)
    
    # urllib3 - requests HTTP, silenciar
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
    
    # requests - silenciar
    logging.getLogger('requests').setLevel(logging.ERROR)
    logging.getLogger('requests.packages').setLevel(logging.ERROR)
    
    # asyncio - pode ser verboso
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    # Pydantic - warnings chatos
    logging.getLogger('pydantic').setLevel(logging.ERROR)
    logging.getLogger('pydantic.main').setLevel(logging.ERROR)
    logging.getLogger('pydantic._internal').setLevel(logging.ERROR)
    
    # Lista completa de loggers chattos para silenciar
    noisy_loggers = [
        'instagrapi.mixins.media',
        'instagrapi.mixins.user', 
        'instagrapi.mixins.private',
        'instagrapi.extractors',
        'pydantic.main',
        'pydantic.validators',
        'pydantic._internal',
        'urllib3.connectionpool',
        'requests.packages.urllib3'
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)
    
    print("📝 Sistema de logging configurado")
    print(f"📁 Logs detalhados: data/logs/{settings.log_file}")
    print("🖥️ Console: só avisos importantes")


# Função para prints importantes que sempre aparecem no console
def console_print(message: str, level: str = "info"):
    """
    Print que sempre aparece no console, independente do nível de log
    
    Args:
        message: Mensagem para exibir
        level: Nível (info, success, warning, error)
    """
    emojis = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️", 
        "error": "❌",
        "loading": "🔄"
    }
    
    emoji = emojis.get(level, "ℹ️")
    
    # No Windows, usar texto simples
    if sys.platform == "win32":
        symbols = {
            "info": "[INFO]",
            "success": "[OK]",
            "warning": "[WARNING]",
            "error": "[ERROR]",
            "loading": "[...]"
        }
        symbol = symbols.get(level, "[INFO]")
        print(f"{symbol} {message}")
    else:
        print(f"{emoji} {message}")


# Classe para log contextual da aplicação
class AppLogger:
    """Logger específico da aplicação com níveis apropriados"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def info(self, message: str, console: bool = False):
        """Log INFO - vai para arquivo"""
        self.logger.info(message)
        if console:
            console_print(message, "info")
    
    def success(self, message: str, console: bool = True):
        """Log de sucesso - importante, vai para console"""
        self.logger.info(f"SUCCESS: {message}")
        if console:
            console_print(message, "success")
    
    def warning(self, message: str, console: bool = True):
        """Log WARNING - vai para arquivo e console"""
        self.logger.warning(message)
        if console:
            console_print(message, "warning")
    
    def error(self, message: str, console: bool = True):
        """Log ERROR - vai para arquivo e console"""
        self.logger.error(message)
        if console:
            console_print(message, "error")
    
    def loading(self, message: str, console: bool = True):
        """Log de loading/processo - só console"""
        if console:
            console_print(message, "loading")


# Função para obter logger da aplicação
def get_app_logger(name: str) -> AppLogger:
    """
    Obtém logger da aplicação
    
    Args:
        name: Nome do logger
        
    Returns:
        AppLogger configurado
    """
    return AppLogger(name)