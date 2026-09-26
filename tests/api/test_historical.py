from datetime import datetime, timezone
from decimal import Decimal


def row():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "symbol": "BTC", "window_start": start, "window_end": start.replace(minute=1),
        "open_price": Decimal("100"), "high_price": Decimal("110"), "low_price": Decimal("90"),
        "close_price": Decimal("105"), "vwap": Decimal("101.5"), "volume": Decimal("2.5"),
        "quote_volume": Decimal("253.75"), "trade_count": 7,
    }


def test_historical_returns_renamed_fields(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [row()]
    conn.fetchval_result = 1
    body = client.get("/api/v1/historical/BTC").json()
    assert body[0]["vwap"] == "101.5"
    assert body[0]["quote_volume"] == "253.75"
    assert "avg_price" not in body[0] and "volume_sum" not in body[0]


def test_naive_query_times_are_treated_as_utc(fakes):
    client, conn, _ = fakes
    client.get("/api/v1/historical/BTC?start_time=2026-01-01T00:00:00&end_time=2026-01-01T01:00:00")
    _, args = conn.queries[0]
    assert args[1] == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert args[2] == datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)


def test_stats_average_is_volume_weighted(fakes):
    client, conn, _ = fakes
    conn.fetchrow_result = {"lowest": Decimal("90"), "highest": Decimal("110"), "average": Decimal("101"),
                            "total_volume": Decimal("5000"), "candle_count": 3}
    client.get("/api/v1/historical/BTC/stats")
    sql, _ = conn.queries[0]
    assert "SUM(p.quote_volume) / NULLIF(SUM(p.volume), 0)" in sql
