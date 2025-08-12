# app/api/responses.py
"""
Response models para a API FastAPI
Estruturas de dados otimizadas para N8N
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import base64

class AccountIn(BaseModel):
    username: str = Field(..., description="Username do Instagram", examples=["usuario.teste"])
    password: str = Field(..., description="Senha da conta", min_length=1)
    proxy: Optional[str] = Field(None, description="Proxy opcional (ex: http://user:pass@host:port)")

class AccountBatchIn(BaseModel):
    accounts: List[AccountIn] = Field(..., min_items=1, description="Lista de contas")

class AccountOut(BaseModel):
    username: str
    status: str
    health_score: float
    operations_today: int
    last_used: Optional[datetime] = None
    available: bool

class AccountsListResponse(BaseModel):
    total: int
    accounts: List[AccountOut]

class OperationResult(BaseModel):
    success: bool
    message: str
    details: Optional[Dict] = None
    
class MediaFileResponse(BaseModel):
    """Response model para arquivo de mídia"""
    id: str = Field(description="ID único do arquivo")
    type: str = Field(description="Tipo de mídia: image, video, carousel")
    filename: str = Field(description="Nome do arquivo")
    size_bytes: int = Field(description="Tamanho em bytes")
    binary_data_base64: str = Field(description="Dados binários em base64")
    metadata: Dict[str, Any] = Field(default={}, description="Metadados da mídia")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "story_123456",
                "type": "image",
                "filename": "story_123456_usuario.jpg",
                "size_bytes": 245760,
                "binary_data_base64": "/9j/4AAQSkZJRgABAQEA...",
                "metadata": {
                    "taken_at": "2024-08-05T10:30:00",
                    "is_story": True,
                    "username": "usuario",
                    "hours_old": 2.5
                }
            }
        }


class CollectionDataResponse(BaseModel):
    """Response model para dados coletados"""
    stories: List[MediaFileResponse] = Field(default=[], description="Stories coletados")
    feed_posts: List[MediaFileResponse] = Field(default=[], description="Posts do feed coletados")


class StatisticsResponse(BaseModel):
    """Response model para estatísticas da coleta"""
    total_files: int = Field(description="Total de arquivos coletados")
    total_size_mb: float = Field(description="Tamanho total em MB")
    stories_count: int = Field(description="Quantidade de stories")
    feed_posts_count: int = Field(description="Quantidade de posts do feed")
    collection_time_seconds: Optional[float] = Field(None, description="Tempo de coleta em segundos")


class CollectionResponse(BaseModel):
    """Response principal da coleta"""
    success: bool = Field(description="Se a coleta foi bem-sucedida")
    username: str = Field(description="Username do Instagram coletado")
    timestamp: datetime = Field(description="Timestamp da coleta")
    account_used: Optional[str] = Field(None, description="Conta do pool utilizada")
    data: CollectionDataResponse = Field(description="Dados coletados")
    statistics: StatisticsResponse = Field(description="Estatísticas da coleta")
    error: Optional[str] = Field(None, description="Mensagem de erro se houver")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "username": "cristiano",
                "timestamp": "2024-08-05T15:30:00Z",
                "account_used": "conta_pool_1",
                "data": {
                    "stories": [
                        {
                            "id": "story_123456",
                            "type": "image", 
                            "filename": "story_123456_cristiano.jpg",
                            "size_bytes": 245760,
                            "binary_data_base64": "/9j/4AAQSkZJRgABAQEA...",
                            "metadata": {
                                "taken_at": "2024-08-05T10:30:00",
                                "is_story": True
                            }
                        }
                    ],
                    "feed_posts": []
                },
                "statistics": {
                    "total_files": 1,
                    "total_size_mb": 0.24,
                    "stories_count": 1,
                    "feed_posts_count": 0
                }
            }
        }


class HealthResponse(BaseModel):
    """Response model para health check"""
    status: str = Field(description="Status da API")
    timestamp: datetime = Field(description="Timestamp do health check")
    version: str = Field(default="1.0.0", description="Versão da API")
    pool_status: Dict[str, Any] = Field(description="Status do pool de contas")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-08-05T15:30:00Z", 
                "version": "1.0.0",
                "pool_status": {
                    "total_accounts": 5,
                    "available_accounts": 3,
                    "average_health_score": 95.5
                }
            }
        }


class PoolStatusResponse(BaseModel):
    """Response model para status do pool"""
    total_accounts: int = Field(description="Total de contas no pool")
    available_accounts: int = Field(description="Contas disponíveis para uso")
    status_breakdown: Dict[str, int] = Field(description="Breakdown por status")
    average_health_score: float = Field(description="Score médio de saúde")
    total_operations_today: int = Field(description="Total de operações hoje")
    last_health_check: datetime = Field(description="Último health check")
    
    class Config:
        schema_extra = {
            "example": {
                "total_accounts": 5,
                "available_accounts": 3,
                "status_breakdown": {
                    "active": 3,
                    "cooldown": 1,
                    "dead": 1
                },
                "average_health_score": 95.5,
                "total_operations_today": 25,
                "last_health_check": "2024-08-05T15:30:00Z"
            }
        }


class ErrorResponse(BaseModel):
    """Response model para erros"""
    error: str = Field(description="Mensagem de erro")
    detail: Optional[str] = Field(None, description="Detalhes do erro")
    timestamp: datetime = Field(description="Timestamp do erro")
    username: Optional[str] = Field(None, description="Username relacionado ao erro")
    
    class Config:
        schema_extra = {
            "example": {
                "error": "Usuário não encontrado",
                "detail": "O usuário @inexistente não foi encontrado no Instagram",
                "timestamp": "2024-08-05T15:30:00Z",
                "username": "inexistente"
            }
        }


class APIInfoResponse(BaseModel):
    """Response model para informações da API"""
    name: str = Field(default="Instagram Collection API", description="Nome da API")
    version: str = Field(default="1.0.0", description="Versão da API")
    description: str = Field(default="API para coleta de stories e posts do Instagram", description="Descrição")
    endpoints: Dict[str, str] = Field(description="Endpoints disponíveis")
    documentation: str = Field(default="/docs", description="URL da documentação")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Instagram Collection API",
                "version": "1.0.0", 
                "description": "API para coleta de stories e posts do Instagram",
                "endpoints": {
                    "collect": "POST /collect/{username}",
                    "health": "GET /health",
                    "pool_status": "GET /pool-status"
                },
                "documentation": "/docs"
            }
        }


# Utility functions para conversão
def convert_media_file_to_response(media_file, include_binary: bool = True) -> MediaFileResponse:
    """
    Converte MediaFile para MediaFileResponse
    
    Args:
        media_file: Objeto MediaFile
        include_binary: Se deve incluir dados binários
        
    Returns:
        MediaFileResponse formatado
    """
    # Converter binary_data para base64
    binary_base64 = ""
    if include_binary and hasattr(media_file, 'binary_data'):
        binary_base64 = base64.b64encode(media_file.binary_data).decode('utf-8')
    
    return MediaFileResponse(
        id=str(media_file.id),
        type=str(media_file.type),
        filename=media_file.filename,
        size_bytes=media_file.size_bytes,
        binary_data_base64=binary_base64,
        metadata=media_file.metadata
    )


def convert_collection_result_to_response(result: Dict[str, Any], 
                                        collection_start_time: Optional[float] = None) -> CollectionResponse:
    """
    Converte resultado da coleta para response formatado
    
    Args:
        result: Resultado do CollectionService
        collection_start_time: Timestamp de início da coleta
        
    Returns:
        CollectionResponse formatado
    """
    import time
    
    # Converter stories
    stories_response = []
    for story_data in result.get('data', {}).get('stories', []):
        # Converter binary_data para base64
        binary_base64 = base64.b64encode(story_data['binary_data']).decode('utf-8')
        
        stories_response.append(MediaFileResponse(
            id=story_data['id'],
            type=story_data['type'],
            filename=story_data['filename'],
            size_bytes=story_data['size_bytes'],
            binary_data_base64=binary_base64,
            metadata=story_data['metadata']
        ))
    
    # Converter feed posts
    posts_response = []
    for post_data in result.get('data', {}).get('feed_posts', []):
        # Converter binary_data para base64
        binary_base64 = base64.b64encode(post_data['binary_data']).decode('utf-8')
        
        posts_response.append(MediaFileResponse(
            id=post_data['id'],
            type=post_data['type'],
            filename=post_data['filename'],
            size_bytes=post_data['size_bytes'],
            binary_data_base64=binary_base64,
            metadata=post_data['metadata']
        ))
    
    # Calcular tempo de coleta
    collection_time = None
    if collection_start_time:
        collection_time = time.time() - collection_start_time
    
    # Montar estatísticas
    stats = result.get('statistics', {})
    statistics = StatisticsResponse(
        total_files=stats.get('total_files', 0),
        total_size_mb=stats.get('total_size_mb', 0.0),
        stories_count=stats.get('stories_count', 0),
        feed_posts_count=stats.get('feed_posts_count', 0),
        collection_time_seconds=collection_time
    )
    
    # Montar dados
    data = CollectionDataResponse(
        stories=stories_response,
        feed_posts=posts_response
    )
    
    # Converter timestamp
    timestamp = datetime.fromisoformat(result['timestamp'].replace('Z', '+00:00'))
    
    return CollectionResponse(
        success=result['success'],
        username=result['username'],
        timestamp=timestamp,
        account_used=result.get('account_used'),
        data=data,
        statistics=statistics,
        error=result.get('error')
    )