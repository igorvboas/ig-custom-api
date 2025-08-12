# app/config_clean.py
"""
Configurações limpas sem imports circulares
"""
import os
from typing import Optional


class Settings:
    """Configurações da aplicação - versão limpa"""
    
    def __init__(self):
        # Carregar .env se existir
        self._load_env()
        
        # API Settings
        self.api_host = os.getenv("API_HOST", "0.0.0.0")
        self.api_port = int(os.getenv("API_PORT", "8000"))
        self.api_workers = int(os.getenv("API_WORKERS", "4"))
        
        # Instagram Settings
        self.session_dir = os.getenv("SESSION_DIR", "data/sessions")
        self.downloads_dir = os.getenv("DOWNLOADS_DIR", "data/temp_downloads")
        
        # Pool Settings
        self.max_accounts = int(os.getenv("MAX_ACCOUNTS", "30"))
        self.account_cooldown_minutes = int(os.getenv("ACCOUNT_COOLDOWN_MINUTES", "120"))
        self.max_daily_operations_per_account = int(os.getenv("MAX_DAILY_OPERATIONS_PER_ACCOUNT", "100"))
        self.health_check_interval_minutes = int(os.getenv("HEALTH_CHECK_INTERVAL_MINUTES", "15"))
        
        # Request Settings
        self.request_delay_min = float(os.getenv("REQUEST_DELAY_MIN", "1.0"))
        self.request_delay_max = float(os.getenv("REQUEST_DELAY_MAX", "3.0"))
        self.download_timeout = int(os.getenv("DOWNLOAD_TIMEOUT", "30"))
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_file = os.getenv("LOG_FILE", "instagram_api.log")
        
        # Proxy Settings
        self.default_proxy = os.getenv("DEFAULT_PROXY")
        self.proxy_rotation = os.getenv("PROXY_ROTATION", "false").lower() == "true"
    
    def _load_env(self):
        """Carrega arquivo .env se existir"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass  # dotenv não instalado, usar só variáveis de ambiente