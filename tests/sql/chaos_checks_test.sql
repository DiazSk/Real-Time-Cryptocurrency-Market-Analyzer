-- Run after configs/init-db.sql (the CI schema job runs it after schema_checks.sql).
-- Seeds ETH with a known gap and one bad candle, then asserts benchmarks/checks.sql reports exactly that.
\i benchmarks/checks.sql

CREATE TEMP TABLE cc AS SELECT date_trunc('hour', now()) - INTERVAL '5 hours' AS base;

-- trade_ids 1-10 and 13-20 (gap of 2) inside minute base+1m; 21 inside minute base+2m.
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT c.id, g, 100, 1, 'buy', g, (SELECT base FROM cc) + INTERVAL '1 minute' + g * INTERVAL '1 second', now()
FROM cryptocurrencies c, generate_series(1, 20) g
WHERE c.symbol = 'ETH' AND g NOT IN (11, 12);
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT c.id, 21, 100, 1, 'buy', 21, (SELECT base FROM cc) + INTERVAL '2 minutes 5 seconds', now()
FROM cryptocurrencies c WHERE c.symbol = 'ETH';
-- trade 30 is outside the window: it must not add a gap of 8.
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT c.id, 30, 100, 1, 'buy', 30, (SELECT base FROM cc) + INTERVAL '20 minutes', now()
FROM cryptocurrencies c WHERE c.symbol = 'ETH';

-- Minute base+1m has 18 trades but the candle says 17 (a mismatch); base+2m is correct.
INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, low_price,
                                 close_price, vwap, volume, quote_volume, trade_count)
SELECT c.id, b, b + INTERVAL '1 minute', 100, 100, 100, 100, 100, 17, 1700, 17
FROM cryptocurrencies c, (SELECT base + INTERVAL '1 minute' AS b FROM cc) t WHERE c.symbol = 'ETH';
INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, low_price,
                                 close_price, vwap, volume, quote_volume, trade_count)
SELECT c.id, b, b + INTERVAL '1 minute', 100, 100, 100, 100, 100, 1, 100, 1
FROM cryptocurrencies c, (SELECT base + INTERVAL '2 minutes' AS b FROM cc) t WHERE c.symbol = 'ETH';

DO $$
DECLARE
  t0 timestamptz := (SELECT base FROM cc);
  t1 timestamptz := (SELECT base FROM cc) + INTERVAL '10 minutes';
  g bigint;
  m bigint;
BEGIN
  SELECT gaps INTO g FROM chaos_gaps(t0, t1) WHERE symbol = 'ETH';
  IF g IS DISTINCT FROM 2 THEN RAISE EXCEPTION 'chaos_gaps: expected 2 for ETH, got %', g; END IF;
  SELECT count(*) INTO m FROM chaos_candle_mismatches(t0, t1);
  IF m <> 1 THEN RAISE EXCEPTION 'chaos_candle_mismatches: expected 1 row, got %', m; END IF;
END $$;

\echo 'chaos_checks: ALL PASSED'
