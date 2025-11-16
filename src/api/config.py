"""
API Configuration Settings
Phase 4 - Week 8
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables or .env file
    """
    
    # API Settings
    API_TITLE: str = "Crypto Market Analyzer API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Real-time cryptocurrency market data API"
    
    # Server Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_DECODE_RESPONSES: bool = True
    
    # PostgreSQL Settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "crypto_user"
    POSTGRES_PASSWORD: str = "crypto_pass"
    POSTGRES_DB: str = "crypto_db"
    
    # CORS Settings
    CORS_ORIGINS: list = ["http://localhost:8501", "http://localhost:3000"]
    
    # Cache Settings
    CACHE_TTL_SECONDS: int = 60  # Cache query results for 60 seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
