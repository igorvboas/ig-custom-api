from datetime import datetime, timedelta

# models.py
"""
Modelos de dados para a API
"""
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import json


class AccountStatus(str, Enum):
    """Status da conta Instagram"""
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    DEAD = "dead"
    CHALLENGE = "challenge"
    LOGIN_REQUIRED = "login_required"


class MediaType(str, Enum):
    """Tipo de mídia"""
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"


class InstagramAccount(BaseModel):
    """Modelo da conta Instagram"""
    username: str
    password: str
    proxy: Optional[str] = None
    session_file: str
    status: AccountStatus = AccountStatus.ACTIVE
    last_used: Optional[datetime] = None
    operations_today: int = 0
    health_score: float = 100.0
    total_operations: int = 0
    total_errors: int = 0
    created_at: datetime = datetime.now()
    
    def is_available(self) -> bool:
        """Verifica se a conta está disponível para uso"""
        if self.status != AccountStatus.ACTIVE:
            return False
            
        # Verifica cooldown
        if self.last_used:
            cooldown_time = timedelta(minutes=120)  # 2 horas
            if datetime.now() - self.last_used < cooldown_time:
                return False
        
        # Verifica limite diário
        if self.operations_today >= 100:
            return False
            
        return True
    
    def update_health_score(self, success: bool):
        """Atualiza score de saúde baseado no sucesso/falha"""
        if success:
            self.health_score = min(100.0, self.health_score + 1.0)
        else:
            self.health_score = max(0.0, self.health_score - 5.0)
            self.total_errors += 1
    
    def mark_used(self):
        """Marca conta como usada"""
        self.last_used = datetime.now()
        self.operations_today += 1
        self.total_operations += 1


class MediaFile(BaseModel):
    """Modelo de arquivo de mídia coletado"""
    id: str
    type: MediaType
    binary_data: bytes
    filename: str
    size_bytes: int
    metadata: Dict[str, Any] = {}
    
    class Config:
        arbitrary_types_allowed = True


class CollectionResult:
    """Resultado da coleta de mídias"""
    
    def __init__(self, username: str, timestamp = None, 
                 stories = None, feed_posts = None,
                 success: bool = True, error_message = None, 
                 account_used = None):
        
        from datetime import datetime
        
        self.username = username
        self.timestamp = timestamp if timestamp else datetime.now()
        self.stories = stories if stories else []
        self.feed_posts = feed_posts if feed_posts else []
        self.success = success
        self.error_message = error_message
        self.account_used = account_used