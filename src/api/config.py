"""
API Configuration Settings
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
    CORS_ORIGINS: list = ["http://localhost:3000"]

    # Dev-friendly regex: any port on localhost/127.0.0.1 and common LAN ranges
    # (RFC1918 192.168.x.x and 10.x.x.x). Matches in addition to CORS_ORIGINS.
    # Tighten or set to None for prod.
    CORS_ORIGIN_REGEX: str = (
        r"^http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):\d+$"
    )

    # Cache Settings
    CACHE_TTL_SECONDS: int = 60  # Cache query results for 60 seconds

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Create global settings instance
settings = Settings()
