"""
Tracked-symbol registry.

The cryptocurrencies table is the only list of tracked symbols. The producer
reads it to know which Coinbase products to subscribe to, and the API reads it
to validate symbols and serve /api/v1/symbols.
"""

from typing import NamedTuple


class Symbol(NamedTuple):
    symbol: str
    name: str
    coingecko_id: str
    coinbase_product: str


SYMBOLS_SQL = """
    SELECT symbol, name, coingecko_id, coinbase_product
    FROM cryptocurrencies
    WHERE is_active
    ORDER BY id
"""


async def fetch_symbols(conn) -> dict[str, Symbol]:
    """Return active symbols keyed by ticker, in table order. `conn` may be an asyncpg connection or pool."""
    rows = await conn.fetch(SYMBOLS_SQL)
    if not rows:
        raise RuntimeError(
            "cryptocurrencies has no active symbols; was configs/init-db.sql applied?"
        )
    return {
        r["symbol"]: Symbol(r["symbol"], r["name"], r["coingecko_id"], r["coinbase_product"])
        for r in rows
    }
