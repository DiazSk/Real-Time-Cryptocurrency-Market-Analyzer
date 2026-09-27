-- Sub-project 3: analytics layer. Idempotent: `make migrate` on existing volumes, and mounted
-- as docker-entrypoint-initdb.d/zz-analytics.sql so fresh volumes run it after init-db.sql.

-- Official Coinbase 1-minute candles, kept apart from the pipeline's own price_aggregates_1m
-- so the two can be reconciled.
CREATE TABLE IF NOT EXISTS coinbase_candles_1m (
    crypto_id  INTEGER         NOT NULL REFERENCES cryptocurrencies(id),
    bucket     TIMESTAMPTZ     NOT NULL,
    open       DECIMAL(20, 8)  NOT NULL,
    high       DECIMAL(20, 8)  NOT NULL,
    low        DECIMAL(20, 8)  NOT NULL,
    close      DECIMAL(20, 8)  NOT NULL,
    volume     DECIMAL(28, 10) NOT NULL CHECK (volume >= 0),
    loaded_at  TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (crypto_id, bucket)
);
SELECT create_hypertable('coinbase_candles_1m', 'bucket',
                         chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('coinbase_candles_1m', INTERVAL '120 days', if_not_exists => TRUE);

-- Trades repaired from the REST API are marked, and have no feed sequence number.
ALTER TABLE raw_trades ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'stream';
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'raw_trades_source_check') THEN
    ALTER TABLE raw_trades ADD CONSTRAINT raw_trades_source_check CHECK (source IN ('stream', 'rest_backfill'));
  END IF;
END $$;
ALTER TABLE raw_trades ALTER COLUMN sequence DROP NOT NULL;

\echo 'Migration 001_analytics applied'
