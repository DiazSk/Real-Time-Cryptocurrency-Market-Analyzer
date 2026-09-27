"""Candle recompute from raw_trades, shared by the lite consumer and the trade-gap repair."""

# Recomputes the candle straight from the persisted raw_trades rows for the window,
# rather than from in-memory sums — so a replay after a crash-restart (which can
# only ever see a subset or the full set of that window's trades, never spurious
# ones, thanks to raw_trades' own idempotent insert) always produces the complete,
# correct candle. It can never write a partial candle over a complete one.
CANDLE_UPSERT_FROM_RAW_SQL = """
INSERT INTO price_aggregates_1m
    (crypto_id, window_start, window_end, open_price, high_price, low_price,
     close_price, vwap, volume, quote_volume, trade_count)
SELECT
    crypto_id,
    %s,
    %s,
    (array_agg(price ORDER BY event_time, trade_id))[1],
    max(price),
    min(price),
    (array_agg(price ORDER BY event_time DESC, trade_id DESC))[1],
    sum(price * size) / sum(size),
    sum(size),
    sum(price * size),
    count(*)
FROM raw_trades
WHERE crypto_id = (SELECT id FROM cryptocurrencies WHERE symbol = %s)
  AND event_time >= %s
  AND event_time < %s
GROUP BY crypto_id
ON CONFLICT (crypto_id, window_start) DO UPDATE SET
    window_end   = EXCLUDED.window_end,
    open_price   = EXCLUDED.open_price,
    high_price   = EXCLUDED.high_price,
    low_price    = EXCLUDED.low_price,
    close_price  = EXCLUDED.close_price,
    vwap         = EXCLUDED.vwap,
    volume       = EXCLUDED.volume,
    quote_volume = EXCLUDED.quote_volume,
    trade_count  = EXCLUDED.trade_count,
    updated_at   = now()
RETURNING window_start, window_end, open_price, high_price, low_price, close_price,
          vwap, volume, quote_volume, trade_count
"""
