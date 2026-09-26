from datetime import datetime, timezone
from decimal import Decimal

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def test_alerts_include_z_score_and_severity(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [{
        "symbol": "BTC", "alert_type": "PRICE_SPIKE", "severity": "HIGH", "z_score": Decimal("9.5"),
        "price_change_pct": Decimal("5.1"), "old_price": Decimal("100"), "new_price": Decimal("105.1"),
        "window_start": NOW, "window_end": NOW, "created_at": NOW,
    }]
    alert = client.get("/api/v1/alerts/BTC").json()["alerts"][0]
    assert alert["severity"] == "HIGH"
    assert alert["z_score"] == 9.5


def test_all_alerts_pass_null_symbol_filter(fakes):
    client, conn, _ = fakes
    client.get("/api/v1/alerts/ALL")
    _, args = conn.queries[0]
    assert args[0] is None


def test_trending_reads_hourly_rollup_and_keeps_frontend_shape(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [{
        "symbol": "BTC", "name": "Bitcoin", "price": Decimal("105"), "volume_24h": Decimal("1000000"),
        "price_change_24h": Decimal("5.0"), "as_of": NOW,
    }]
    body = client.get("/api/v1/trending?direction=gainers").json()
    sql, _ = conn.queries[0]
    assert "candles_1h" in sql
    assert body["trending"][0] == {
        "symbol": "BTC", "name": "Bitcoin", "price": 105.0, "volume_24h": 1000000.0,
        "market_cap": None, "price_change_24h": 5.0, "timestamp": NOW.isoformat(),
    }


def test_trending_with_under_24h_of_data_is_empty_not_an_error(fakes):
    client, conn, _ = fakes
    r = client.get("/api/v1/trending")
    assert r.status_code == 200
    assert r.json() == {"direction": "abs", "count": 0, "trending": []}
