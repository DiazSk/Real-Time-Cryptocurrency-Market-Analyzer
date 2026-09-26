"""
Access to the tracked-symbol registry that database.lifespan loads into app.state.symbols.
"""

from fastapi import HTTPException

from ..symbols import Symbol


def symbols_of(conn_owner) -> dict[str, Symbol]:
    """The registry for a Request or WebSocket."""
    return conn_owner.app.state.symbols


def require_symbol(symbols: dict[str, Symbol], raw: str, allow_all: bool = False) -> str:
    """Upper-case and validate a path symbol; 400 lists what is supported."""
    symbol = raw.upper()
    if symbol in symbols or (allow_all and symbol == "ALL"):
        return symbol
    supported = ", ".join(symbols) + (", ALL" if allow_all else "")
    raise HTTPException(status_code=400, detail=f"Invalid symbol: {symbol}. Supported: {supported}")
