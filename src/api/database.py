"""
Database Connection Management
Phase 4 - Week 8

Handles PostgreSQL and Redis connections with connection pooling.
"""

import redis
import psycopg2
from psycopg2 import pool
from typing import Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections for PostgreSQL and Redis
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.postgres_pool: Optional[pool.SimpleConnectionPool] = None
        
    def connect_redis(self) -> redis.Redis:
        """
        Create Redis connection with connection pooling
        """
        if self.redis_client is None:
            try:
                self.redis_client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    decode_responses=settings.REDIS_DECODE_RESPONSES,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"✅ Connected to Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            except Exception as e:
                logger.error(f"❌ Redis connection failed: {e}")
                raise
        
        return self.redis_client
    
    def connect_postgres(self) -> pool.SimpleConnectionPool:
        """
        Create PostgreSQL connection pool
        """
        if self.postgres_pool is None:
            try:
                self.postgres_pool = pool.SimpleConnectionPool(
                    minconn=1,
                    maxconn=10,
                    host=settings.POSTGRES_HOST,
                    port=settings.POSTGRES_PORT,
                    database=settings.POSTGRES_DB,
                    user=settings.POSTGRES_USER,
                    password=settings.POSTGRES_PASSWORD
                )
                logger.info(f"✅ Connected to PostgreSQL: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
            except Exception as e:
                logger.error(f"❌ PostgreSQL connection failed: {e}")
                raise
        
        return self.postgres_pool
    
    def get_postgres_connection(self):
        """
        Get a connection from the PostgreSQL pool
        """
        if self.postgres_pool is None:
            self.connect_postgres()
        
        return self.postgres_pool.getconn()
    
    def return_postgres_connection(self, conn):
        """
        Return a connection to the PostgreSQL pool
        """
        if self.postgres_pool is not None:
            self.postgres_pool.putconn(conn)
    
    def close_all(self):
        """
        Close all database connections
        """
        if self.redis_client is not None:
            self.redis_client.close()
            logger.info("Redis connection closed")
        
        if self.postgres_pool is not None:
            self.postgres_pool.closeall()
            logger.info("PostgreSQL connection pool closed")


# Global database manager instance
db_manager = DatabaseManager()


def get_redis() -> redis.Redis:
    """
    Dependency injection for Redis client
    """
    return db_manager.connect_redis()


def get_postgres_connection():
    """
    Dependency injection for PostgreSQL connection
    """
    conn = db_manager.get_postgres_connection()
    try:
        yield conn
    finally:
        db_manager.return_postgres_connection(conn)
