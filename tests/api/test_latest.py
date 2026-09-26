import json
from datetime import datetime, timezone
from decimal import Decimal

from redis.exceptions import ConnectionError as RedisConnectionError

CANDLE_JSON = json.dumps({
    "symbol": "BTC", "windowStart": 1767225600.0, "windowEnd": 1767225660.0,
    "open": 100, "high": 110, "low": 90, "close": 105, "vwap": 101.5,
    "volume": 2.5, "quoteVolume": 253.75, "tradeCount": 7,
})


def db_row(symbol="BTC"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "symbol": symbol, "window_start": start, "window_end": start.replace(minute=1),
        "open_price": Decimal("100"), "high_price": Decimal("110"), "low_price": Decimal("90"),
        "close_price": Decimal("105"), "vwap": Decimal("101.5"), "volume": Decimal("2.5"),
        "quote_volume": Decimal("253.75"), "trade_count": 7,
    }


def test_cache_hit_is_served_from_redis(fakes):
    client, conn, redis = fakes
    redis.store["crypto:BTC:latest"] = CANDLE_JSON
    r = client.get("/api/v1/latest/BTC")
    assert r.status_code == 200
    assert r.headers["X-Data-Source"] == "redis"
    body = r.json()
    assert body["trade_count"] == 7
    assert body["window_start"].startswith("2026-01-01T00:00:00")
    assert conn.queries == []


def test_cache_miss_falls_back_to_postgres(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [db_row()]
    r = client.get("/api/v1/latest/BTC")
    assert r.status_code == 200
    assert r.headers["X-Data-Source"] == "postgres"
    assert Decimal(r.json()["vwap"]) == Decimal("101.5")
    assert conn.queries[0][1] == (["BTC"],)


def test_redis_outage_still_serves_postgres(fakes):
    client, conn, redis = fakes

    async def broken_mget(keys):
        raise RedisConnectionError("redis down")

    redis.mget = broken_mget
    conn.fetch_result = [db_row()]
    r = client.get("/api/v1/latest/BTC")
    assert r.status_code == 200
    assert r.headers["X-Data-Source"] == "postgres"


def test_corrupt_cache_entry_falls_back_to_postgres(fakes):
    client, conn, redis = fakes
    redis.store["crypto:BTC:latest"] = "{not json"
    conn.fetch_result = [db_row()]
    assert client.get("/api/v1/latest/BTC").headers["X-Data-Source"] == "postgres"


def test_no_data_anywhere_is_404(fakes):
    client, _, _ = fakes
    assert client.get("/api/v1/latest/BTC").status_code == 404


def test_all_mixes_sources_and_only_queries_misses(fakes):
    client, conn, redis = fakes
    redis.store["crypto:BTC:latest"] = CANDLE_JSON
    conn.fetch_result = [db_row("POL")]
    r = client.get("/api/v1/latest/all")
    assert r.status_code == 200
    assert set(r.json()["prices"]) == {"BTC", "POL"}
    assert r.headers["X-Cache-Hits"] == "1"
    assert conn.queries[0][1] == (["POL"],)
