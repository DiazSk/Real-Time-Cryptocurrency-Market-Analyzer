import asyncio

import pytest

from src.symbols import Symbol, fetch_symbols


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    async def fetch(self, sql, *args):
        return self.rows


def test_fetch_symbols_keys_by_ticker_in_table_order():
    rows = [
        {"symbol": "BTC", "name": "Bitcoin", "coingecko_id": "bitcoin", "coinbase_product": "BTC-USD"},
        {"symbol": "POL", "name": "Polygon", "coingecko_id": "polygon-ecosystem-token", "coinbase_product": "POL-USD"},
    ]
    symbols = asyncio.run(fetch_symbols(FakeConn(rows)))
    assert list(symbols) == ["BTC", "POL"]
    assert symbols["POL"] == Symbol("POL", "Polygon", "polygon-ecosystem-token", "POL-USD")


def test_fetch_symbols_refuses_empty_table():
    with pytest.raises(RuntimeError, match="init-db.sql"):
        asyncio.run(fetch_symbols(FakeConn([])))
