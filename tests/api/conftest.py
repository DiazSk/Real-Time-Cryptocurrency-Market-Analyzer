import pytest
from fastapi.testclient import TestClient

from src.api.database import get_db, get_pool, get_redis
from src.api.main import app
from src.symbols import Symbol

SYMBOLS = {
    "BTC": Symbol("BTC", "Bitcoin", "bitcoin", "BTC-USD"),
    "POL": Symbol("POL", "Polygon", "polygon-ecosystem-token", "POL-USD"),
}


class FakeConn:
    """Stands in for an asyncpg connection or pool: returns canned rows and records every query."""

    def __init__(self):
        self.fetch_result = []
        self.fetchrow_result = None
        self.fetchval_result = 0
        self.queries = []

    async def fetch(self, sql, *args):
        self.queries.append((sql, args))
        return self.fetch_result

    async def fetchrow(self, sql, *args):
        self.queries.append((sql, args))
        return self.fetchrow_result

    async def fetchval(self, sql, *args):
        self.queries.append((sql, args))
        return self.fetchval_result


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)


@pytest.fixture
def fakes():
    conn, redis = FakeConn(), FakeRedis()
    app.state.symbols = SYMBOLS

    async def _db():
        yield conn

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_pool] = lambda: conn
    app.dependency_overrides[get_redis] = lambda: redis
    # No `with` block: the lifespan (real DB/Redis connections) must not run in unit tests.
    yield TestClient(app), conn, redis
    app.dependency_overrides.clear()
