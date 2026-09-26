-- Real-Time Cryptocurrency Market Analyzer — database schema.
-- The cryptocurrencies table is the only list of tracked symbols: the producer,
-- the API and the Flink sinks (via SQL sub-selects) all read it.

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================
-- 1. Tracked symbols
-- ============================================
CREATE TABLE IF NOT EXISTS cryptocurrencies (
    id               SERIAL       PRIMARY KEY,
    symbol           VARCHAR(10)  NOT NULL UNIQUE,
    name             VARCHAR(100) NOT NULL,
    coingecko_id     VARCHAR(50)  NOT NULL UNIQUE,   -- frontend slug for CoinGecko pages
    coinbase_product VARCHAR(20)  NOT NULL UNIQUE,   -- Coinbase Exchange product id
    is_active        BOOLEAN      NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

INSERT INTO cryptocurrencies (symbol, name, coingecko_id, coinbase_product) VALUES
    ('BTC',  'Bitcoin',   'bitcoin',                 'BTC-USD'),
    ('ETH',  'Ethereum',  'ethereum',                'ETH-USD'),
    ('SOL',  'Solana',    'solana',                  'SOL-USD'),
    ('XRP',  'XRP',       'ripple',                  'XRP-USD'),
    ('ADA',  'Cardano',   'cardano',                 'ADA-USD'),
    ('DOGE', 'Dogecoin',  'dogecoin',                'DOGE-USD'),
    ('AVAX', 'Avalanche', 'avalanche-2',             'AVAX-USD'),
    ('POL',  'Polygon',   'polygon-ecosystem-token', 'POL-USD')   -- MATIC-USD is delisted on Coinbase
ON CONFLICT (symbol) DO NOTHING;

-- ============================================
-- 2. Raw trades (one row per Coinbase match)
-- ============================================
CREATE TABLE IF NOT EXISTS raw_trades (
    crypto_id   INTEGER         NOT NULL REFERENCES cryptocurrencies(id),
    trade_id    BIGINT          NOT NULL,
    price       DECIMAL(20, 8)  NOT NULL CHECK (price > 0),
    size        DECIMAL(28, 10) NOT NULL CHECK (size > 0),
    side        VARCHAR(4)      NOT NULL CHECK (side IN ('buy', 'sell')),
    sequence    BIGINT          NOT NULL,
    event_time  TIMESTAMPTZ     NOT NULL,   -- exchange trade time (Flink event time)
    ingest_time TIMESTAMPTZ     NOT NULL,   -- producer receive time; ingest_time - event_time = ingestion lag
    PRIMARY KEY (crypto_id, trade_id, event_time)
);
SELECT create_hypertable('raw_trades', 'event_time',
                         chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
SELECT add_retention_policy('raw_trades', INTERVAL '7 days', if_not_exists => TRUE);

-- ============================================
-- 3. 1-minute OHLCV candles (written by Flink, upserted)
-- ============================================
CREATE TABLE IF NOT EXISTS price_aggregates_1m (
    crypto_id    INTEGER         NOT NULL REFERENCES cryptocurrencies(id),
    window_start TIMESTAMPTZ     NOT NULL,
    window_end   TIMESTAMPTZ     NOT NULL,
    open_price   DECIMAL(20, 8)  NOT NULL,
    high_price   DECIMAL(20, 8)  NOT NULL,
    low_price    DECIMAL(20, 8)  NOT NULL,
    close_price  DECIMAL(20, 8)  NOT NULL,
    vwap         DECIMAL(20, 8)  NOT NULL,   -- quote_volume / volume
    volume       DECIMAL(28, 10) NOT NULL,   -- base units, e.g. BTC
    quote_volume DECIMAL(28, 8)  NOT NULL,   -- USD: sum(price * size)
    trade_count  INTEGER         NOT NULL CHECK (trade_count > 0),
    updated_at   TIMESTAMPTZ     NOT NULL DEFAULT now(),
    PRIMARY KEY (crypto_id, window_start)
);
SELECT create_hypertable('price_aggregates_1m', 'window_start',
                         chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('price_aggregates_1m', INTERVAL '90 days', if_not_exists => TRUE);

-- ============================================
-- 4. Rollups: continuous aggregates over the 1-minute candles
-- ============================================
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_5m WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT crypto_id,
       time_bucket(INTERVAL '5 minutes', window_start) AS bucket,
       first(open_price, window_start)                 AS open_price,
       max(high_price)                                 AS high_price,
       min(low_price)                                  AS low_price,
       last(close_price, window_start)                 AS close_price,
       sum(volume)                                     AS volume,
       sum(quote_volume)                               AS quote_volume,
       sum(trade_count)                                AS trade_count,
       sum(quote_volume) / NULLIF(sum(volume), 0)      AS vwap
FROM price_aggregates_1m
GROUP BY crypto_id, bucket
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_15m WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT crypto_id,
       time_bucket(INTERVAL '15 minutes', window_start) AS bucket,
       first(open_price, window_start)                  AS open_price,
       max(high_price)                                  AS high_price,
       min(low_price)                                   AS low_price,
       last(close_price, window_start)                  AS close_price,
       sum(volume)                                      AS volume,
       sum(quote_volume)                                AS quote_volume,
       sum(trade_count)                                 AS trade_count,
       sum(quote_volume) / NULLIF(sum(volume), 0)       AS vwap
FROM price_aggregates_1m
GROUP BY crypto_id, bucket
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_1h WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT crypto_id,
       time_bucket(INTERVAL '1 hour', window_start) AS bucket,
       first(open_price, window_start)              AS open_price,
       max(high_price)                              AS high_price,
       min(low_price)                               AS low_price,
       last(close_price, window_start)               AS close_price,
       sum(volume)                                  AS volume,
       sum(quote_volume)                            AS quote_volume,
       sum(trade_count)                             AS trade_count,
       sum(quote_volume) / NULLIF(sum(volume), 0)   AS vwap
FROM price_aggregates_1m
GROUP BY crypto_id, bucket
WITH NO DATA;

-- end_offset keeps the still-open bucket out of the materialization.
SELECT add_continuous_aggregate_policy('candles_5m',
       start_offset => INTERVAL '1 hour', end_offset => INTERVAL '5 minutes',
       schedule_interval => INTERVAL '1 minute', if_not_exists => TRUE);
SELECT add_continuous_aggregate_policy('candles_15m',
       start_offset => INTERVAL '3 hours', end_offset => INTERVAL '15 minutes',
       schedule_interval => INTERVAL '5 minutes', if_not_exists => TRUE);
SELECT add_continuous_aggregate_policy('candles_1h',
       start_offset => INTERVAL '1 day', end_offset => INTERVAL '1 hour',
       schedule_interval => INTERVAL '15 minutes', if_not_exists => TRUE);

SELECT add_retention_policy('candles_5m',  INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('candles_15m', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('candles_1h',  INTERVAL '90 days', if_not_exists => TRUE);

-- ============================================
-- 5. Anomaly alerts (written by Flink, idempotent)
-- ============================================
CREATE TABLE IF NOT EXISTS price_alerts (
    id               SERIAL         PRIMARY KEY,
    crypto_id        INTEGER        NOT NULL REFERENCES cryptocurrencies(id),
    alert_type       VARCHAR(20)    NOT NULL CHECK (alert_type IN ('PRICE_SPIKE', 'PRICE_DROP')),
    severity         VARCHAR(10)    NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')),
    z_score          DECIMAL(10, 4) NOT NULL,   -- Flink clamps to +/-9999
    price_change_pct DECIMAL(10, 4) NOT NULL,
    old_price        DECIMAL(20, 8) NOT NULL,   -- previous candle close
    new_price        DECIMAL(20, 8) NOT NULL,   -- this candle close
    window_start     TIMESTAMPTZ    NOT NULL,
    window_end       TIMESTAMPTZ    NOT NULL,
    created_at       TIMESTAMPTZ    NOT NULL DEFAULT now(),
    UNIQUE (crypto_id, window_start, alert_type)
);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at  ON price_alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_crypto_time ON price_alerts (crypto_id, created_at DESC);

\echo 'Schema ready: cryptocurrencies, raw_trades, price_aggregates_1m, candles_5m/15m/1h, price_alerts'
