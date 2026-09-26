def test_symbols_come_from_the_registry(fakes):
    client, _, _ = fakes
    body = client.get("/api/v1/symbols").json()
    assert body["count"] == 2
    assert {"symbol": "POL", "name": "Polygon", "slug": "polygon-ecosystem-token"} in body["symbols"]


def test_unknown_symbol_is_rejected_with_supported_list(fakes):
    client, _, _ = fakes
    r = client.get("/api/v1/historical/MATIC")
    assert r.status_code == 400
    assert "Supported: BTC, POL" in r.json()["detail"]


def test_alerts_accept_all(fakes):
    client, _, _ = fakes
    assert client.get("/api/v1/alerts/ALL").status_code == 200
