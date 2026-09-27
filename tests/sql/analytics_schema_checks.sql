-- Run after configs/init-db.sql and configs/migrations/001_analytics.sql (twice: it must be idempotent).
DO $$
BEGIN
  IF to_regclass('coinbase_candles_1m') IS NULL THEN RAISE EXCEPTION 'coinbase_candles_1m missing'; END IF;
  IF NOT EXISTS (SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'coinbase_candles_1m') THEN
    RAISE EXCEPTION 'coinbase_candles_1m must be a hypertable';
  END IF;
  IF (SELECT is_nullable FROM information_schema.columns
      WHERE table_name = 'raw_trades' AND column_name = 'sequence') <> 'YES' THEN
    RAISE EXCEPTION 'raw_trades.sequence must be nullable for REST-backfilled trades';
  END IF;
  IF (SELECT column_default FROM information_schema.columns
      WHERE table_name = 'raw_trades' AND column_name = 'source') NOT LIKE '''stream''%' THEN
    RAISE EXCEPTION 'raw_trades.source must default to stream';
  END IF;
  BEGIN
    INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time, source)
    VALUES (1, 999999999, 1, 1, 'buy', NULL, now(), now(), 'bogus');
    RAISE EXCEPTION 'raw_trades.source CHECK constraint missing';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
END $$;

\echo 'analytics_schema_checks: ALL PASSED'
