-- Chaos-test data checks. Loaded by benchmarks/chaos_test.py and tests/sql/chaos_checks_test.sql.
-- Coinbase trade_id rises by exactly 1 per product, so a jump inside the window is a lost trade.

CREATE OR REPLACE FUNCTION chaos_gaps(t0 timestamptz, t1 timestamptz)
RETURNS TABLE (symbol text, gaps bigint) LANGUAGE sql STABLE AS $$
  SELECT c.symbol::text, COALESCE(sum(d.gap) FILTER (WHERE d.gap > 0), 0)::bigint
  FROM (
    SELECT rt.crypto_id,
           rt.trade_id - lag(rt.trade_id) OVER (PARTITION BY rt.crypto_id ORDER BY rt.trade_id) - 1 AS gap
    FROM raw_trades rt
    WHERE rt.event_time >= t0 AND rt.event_time < t1
  ) d
  JOIN cryptocurrencies c ON c.id = d.crypto_id
  GROUP BY c.symbol
  ORDER BY c.symbol
$$;

-- Full minutes inside the window where the candle's trade_count disagrees with raw_trades
-- (or only one side exists). Catches double counting after a Flink recovery.
CREATE OR REPLACE FUNCTION chaos_candle_mismatches(t0 timestamptz, t1 timestamptz)
RETURNS TABLE (symbol text, minute timestamptz, candle_count bigint, raw_count bigint)
LANGUAGE sql STABLE AS $$
  WITH bounds AS (
    SELECT date_trunc('minute', t0) + INTERVAL '1 minute' AS lo, date_trunc('minute', t1) AS hi
  ), r AS (
    SELECT rt.crypto_id, date_trunc('minute', rt.event_time) AS m, count(*) AS n
    FROM raw_trades rt, bounds
    WHERE rt.event_time >= bounds.lo AND rt.event_time < bounds.hi
    GROUP BY 1, 2
  ), p AS (
    SELECT pa.crypto_id, pa.window_start AS m, pa.trade_count::bigint AS n
    FROM price_aggregates_1m pa, bounds
    WHERE pa.window_start >= bounds.lo AND pa.window_end <= bounds.hi
  )
  SELECT c.symbol::text, COALESCE(p.m, r.m), p.n, r.n
  FROM p FULL JOIN r ON p.crypto_id = r.crypto_id AND p.m = r.m
  JOIN cryptocurrencies c ON c.id = COALESCE(p.crypto_id, r.crypto_id)
  WHERE p.n IS DISTINCT FROM r.n
  ORDER BY 1, 2
$$;
