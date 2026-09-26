import pytest


@pytest.mark.parametrize("interval,relation,time_col", [
    ("1m", "price_aggregates_1m", "window_start"),
    ("5m", "candles_5m", "bucket"),
    ("15m", "candles_15m", "bucket"),
    ("1h", "candles_1h", "bucket"),
])
def test_each_interval_queries_the_right_relation(fakes, interval, relation, time_col):
    client, conn, _ = fakes
    client.get(f"/api/v1/historical/BTC?interval={interval}")
    sql, _ = conn.queries[0]
    assert f"FROM {relation} p" in sql
    assert f"p.{time_col} AS window_start" in sql
    assert f"p.{time_col} >= $2" in sql


def test_default_interval_is_1m(fakes):
    client, conn, _ = fakes
    client.get("/api/v1/historical/BTC")
    sql, _ = conn.queries[0]
    assert "FROM price_aggregates_1m p" in sql


def test_bad_interval_gives_422(fakes):
    client, _, _ = fakes
    r = client.get("/api/v1/historical/BTC?interval=3m")
    assert r.status_code == 422


def test_5m_window_end_is_bucket_plus_width(fakes):
    client, conn, _ = fakes
    client.get("/api/v1/historical/BTC?interval=5m")
    sql, _ = conn.queries[0]
    assert "p.bucket + INTERVAL '5 minutes' AS window_end" in sql


def test_stats_endpoint_accepts_interval(fakes):
    client, conn, _ = fakes
    from decimal import Decimal
    conn.fetchrow_result = {"lowest": Decimal("1"), "highest": Decimal("2"), "average": Decimal("1.5"),
                             "total_volume": Decimal("10"), "candle_count": 1}
    r = client.get("/api/v1/historical/BTC/stats?interval=1h")
    assert r.status_code == 200
    sql, _ = conn.queries[0]
    assert "FROM candles_1h p" in sql

    r = client.get("/api/v1/historical/BTC/stats?interval=bogus")
    assert r.status_code == 422
