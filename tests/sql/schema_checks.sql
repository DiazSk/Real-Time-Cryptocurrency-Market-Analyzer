-- Run against a fresh database that has configs/init-db.sql applied.
-- Every check raises an exception on failure; psql -v ON_ERROR_STOP=1 turns that into exit code 3.

DO $$
BEGIN
  IF (SELECT count(*) FROM cryptocurrencies) <> 8 THEN
    RAISE EXCEPTION 'expected 8 seeded symbols';
  END IF;
  IF EXISTS (SELECT 1 FROM cryptocurrencies WHERE symbol = 'MATIC') THEN
    RAISE EXCEPTION 'MATIC must be replaced by POL';
  END IF;
  IF (SELECT coinbase_product FROM cryptocurrencies WHERE symbol = 'POL') <> 'POL-USD' THEN
    RAISE EXCEPTION 'POL must map to POL-USD';
  END IF;
  IF (SELECT count(*) FROM timescaledb_information.hypertables
      WHERE hypertable_name IN ('raw_trades', 'price_aggregates_1m')) <> 2 THEN
    RAISE EXCEPTION 'raw_trades and price_aggregates_1m must be hypertables';
  END IF;
  IF (SELECT count(*) FROM timescaledb_information.continuous_aggregates
      WHERE view_name IN ('candles_5m', 'candles_15m', 'candles_1h')) <> 3 THEN
    RAISE EXCEPTION 'continuous aggregates missing';
  END IF;
  IF to_regclass('raw_price_data') IS NOT NULL
     OR to_regclass('processing_metadata') IS NOT NULL
     OR to_regclass('v_latest_prices') IS NOT NULL THEN
    RAISE EXCEPTION 'legacy objects must be dropped';
  END IF;
END $$;

CREATE TEMP TABLE t0 AS SELECT date_trunc('hour', now()) - INTERVAL '2 hours' AS base;

-- raw_trades: the Flink sink's INSERT ... SELECT ... ON CONFLICT DO NOTHING must be idempotent.
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT id, 1, 100, 0.5, 'buy', 10, (SELECT base FROM t0) + INTERVAL '10 seconds', now()
FROM cryptocurrencies WHERE symbol = 'BTC'
ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING;
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT id, 1, 100, 0.5, 'buy', 10, (SELECT base FROM t0) + INTERVAL '10 seconds', now()
FROM cryptocurrencies WHERE symbol = 'BTC'
ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING;
-- Unknown symbols insert nothing (the sub-select finds no crypto_id).
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT id, 2, 1, 1, 'buy', 1, now(), now() FROM cryptocurrencies WHERE symbol = 'NOPE'
ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING;

DO $$ BEGIN
  IF (SELECT count(*) FROM raw_trades) <> 1 THEN RAISE EXCEPTION 'raw_trades dedup failed'; END IF;
END $$;

-- Two 1-minute candles inside one 5-minute bucket.
INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, low_price,
                                 close_price, vwap, volume, quote_volume, trade_count)
SELECT id, b, b + INTERVAL '1 minute', 100, 110, 90, 105, 101, 2, 202, 3
FROM cryptocurrencies, (SELECT base AS b FROM t0) t WHERE symbol = 'BTC';
INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, low_price,
                                 close_price, vwap, volume, quote_volume, trade_count)
SELECT id, b + INTERVAL '1 minute', b + INTERVAL '2 minutes', 105, 120, 100, 115, 110, 1, 110, 1
FROM cryptocurrencies, (SELECT base AS b FROM t0) t WHERE symbol = 'BTC';

CALL refresh_continuous_aggregate('candles_5m', NULL, NULL);

DO $$
DECLARE r record;
BEGIN
  SELECT * INTO r FROM candles_5m WHERE crypto_id = (SELECT id FROM cryptocurrencies WHERE symbol = 'BTC');
  IF r.open_price <> 100 OR r.high_price <> 120 OR r.low_price <> 90 OR r.close_price <> 115
     OR r.volume <> 3 OR r.quote_volume <> 312 OR r.trade_count <> 4 OR r.vwap <> 104 THEN
    RAISE EXCEPTION 'candles_5m rollup wrong: %', r;
  END IF;
END $$;

-- price_alerts: one alert per (symbol, window, type); severity is constrained.
INSERT INTO price_alerts (crypto_id, alert_type, severity, z_score, price_change_pct, old_price, new_price,
                          window_start, window_end)
SELECT id, 'PRICE_SPIKE', 'HIGH', 9.5, 5.1, 100, 105.1, b, b + INTERVAL '1 minute'
FROM cryptocurrencies, (SELECT base AS b FROM t0) t WHERE symbol = 'BTC'
ON CONFLICT (crypto_id, window_start, alert_type) DO NOTHING;
INSERT INTO price_alerts (crypto_id, alert_type, severity, z_score, price_change_pct, old_price, new_price,
                          window_start, window_end)
SELECT id, 'PRICE_SPIKE', 'HIGH', 9.5, 5.1, 100, 105.1, b, b + INTERVAL '1 minute'
FROM cryptocurrencies, (SELECT base AS b FROM t0) t WHERE symbol = 'BTC'
ON CONFLICT (crypto_id, window_start, alert_type) DO NOTHING;

DO $$
BEGIN
  IF (SELECT count(*) FROM price_alerts) <> 1 THEN RAISE EXCEPTION 'price_alerts dedup failed'; END IF;
  BEGIN
    INSERT INTO price_alerts (crypto_id, alert_type, severity, z_score, price_change_pct, old_price, new_price,
                              window_start, window_end)
    VALUES (1, 'PRICE_DROP', 'EXTREME', 5, -5, 100, 95, now(), now());
    RAISE EXCEPTION 'severity CHECK constraint missing';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
END $$;

\echo 'schema_checks: ALL PASSED'
