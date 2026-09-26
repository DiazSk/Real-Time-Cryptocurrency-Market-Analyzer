"""
Database connection management using async drivers.

Pool lifecycle is managed by the FastAPI lifespan context and stored on app.state
to prevent connection leaks under concurrent async load.  Dependency functions pull
connections from app.state so they are never re-initialised per request.
"""

import asyncpg
import redis.asyncio as aioredis
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from .config import settings
from .pubsub import pubsub_dispatcher
from ..symbols import fetch_symbols

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise and tear down all database connections for the application lifetime."""
    app.state.db_pool = await asyncpg.create_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        min_size=1,
        max_size=10,
    )
    app.state.symbols = await fetch_symbols(app.state.db_pool)
    app.state.redis = aioredis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
        decode_responses=settings.REDIS_DECODE_RESPONSES,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    logger.info("Connected to PostgreSQL (%s:%s) and Redis (%s:%s) (%d symbols)",
                settings.POSTGRES_HOST, settings.POSTGRES_PORT,
                settings.REDIS_HOST, settings.REDIS_PORT,
                len(app.state.symbols))
    pubsub_dispatcher.start(app.state.redis)
    yield
    await pubsub_dispatcher.stop()
    await app.state.db_pool.close()
    await app.state.redis.aclose()
    logger.info("Database connections closed")


async def get_db(request: Request):
    """Yields an asyncpg connection acquired from the pool on app.state."""
    async with request.app.state.db_pool.acquire() as conn:
        yield conn


async def get_redis(request: Request) -> aioredis.Redis:
    """Returns the shared async Redis client from app.state."""
    return request.app.state.redis


async def get_pool(request: Request) -> asyncpg.Pool:
    """The shared pool, for handlers that only sometimes need the database (e.g. cache fallback)."""
    return request.app.state.db_pool
