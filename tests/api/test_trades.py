def test_recent_trades_returns_time_price_oldest_first(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [
        {"time": 1_790_000_000.25, "price": 84000.5},
        {"time": 1_790_000_001.0, "price": 84001.0},
    ]

    res = client.get("/api/v1/trades/btc?seconds=60")

    assert res.status_code == 200
    body = res.json()
    assert body["symbol"] == "BTC" and body["seconds"] == 60
    assert body["trades"] == [
        {"time": 1_790_000_000.25, "price": 84000.5},
        {"time": 1_790_000_001.0, "price": 84001.0},
    ]
    sql, args = conn.queries[-1]
    assert "raw_trades" in sql and "ORDER BY t.event_time ASC" in sql
    assert args == ("BTC", 60)


def test_recent_trades_rejects_unknown_symbol(fakes):
    client, _, _ = fakes
    assert client.get("/api/v1/trades/NOPE").status_code == 400


def test_recent_trades_caps_window_at_300s(fakes):
    client, _, _ = fakes
    assert client.get("/api/v1/trades/BTC?seconds=301").status_code == 422
    assert client.get("/api/v1/trades/BTC?seconds=300").status_code == 200
