-- Real-Time Cryptocurrency Market Analyzer Database Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- ============================================
-- 1. CRYPTOCURRENCIES TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS cryptocurrencies (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    coingecko_id VARCHAR(50) UNIQUE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO cryptocurrencies (symbol, name, coingecko_id) VALUES
    ('BTC', 'Bitcoin', 'bitcoin'),
    ('ETH', 'Ethereum', 'ethereum')
ON CONFLICT (symbol) DO NOTHING;

-- ============================================
-- 2. RAW PRICE DATA TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS raw_price_data (
    id BIGSERIAL,
    crypto_id INTEGER NOT NULL REFERENCES cryptocurrencies(id),
    price DECIMAL(20, 8) NOT NULL,
    volume_24h DECIMAL(20, 2),
    market_cap DECIMAL(20, 2),
    price_change_24h DECIMAL(10, 4),
    timestamp TIMESTAMP NOT NULL,
    kafka_offset BIGINT,
    kafka_partition INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, timestamp)
);

SELECT create_hypertable('raw_price_data', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_raw_price_crypto_id ON raw_price_data(crypto_id);
CREATE INDEX IF NOT EXISTS idx_raw_price_timestamp ON raw_price_data(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_raw_price_crypto_timestamp ON raw_price_data(crypto_id, timestamp DESC);

-- ============================================
-- 3. AGGREGATED PRICE DATA (1-minute windows)
-- ============================================

CREATE TABLE IF NOT EXISTS price_aggregates_1m (
    id BIGSERIAL,
    crypto_id INTEGER NOT NULL REFERENCES cryptocurrencies(id),
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    open_price DECIMAL(20, 8) NOT NULL,
    high_price DECIMAL(20, 8) NOT NULL,
    low_price DECIMAL(20, 8) NOT NULL,
    close_price DECIMAL(20, 8) NOT NULL,
    avg_price DECIMAL(20, 8) NOT NULL,
    volume_sum DECIMAL(20, 2),
    trade_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(crypto_id, window_start),
    PRIMARY KEY (id, window_start)
);

-- Convert to hypertable so TimescaleDB retention policy can be applied.
-- A plain PostgreSQL table cannot have add_retention_policy called on it.
SELECT create_hypertable('price_aggregates_1m', 'window_start', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_agg_1m_crypto_id ON price_aggregates_1m(crypto_id);
CREATE INDEX IF NOT EXISTS idx_agg_1m_window_start ON price_aggregates_1m(window_start DESC);
CREATE INDEX IF NOT EXISTS idx_agg_1m_crypto_window ON price_aggregates_1m(crypto_id, window_start DESC);

-- ============================================
-- 4. PRICE ALERTS TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS price_alerts (
    id SERIAL PRIMARY KEY,
    crypto_id INTEGER NOT NULL REFERENCES cryptocurrencies(id),
    alert_type VARCHAR(20) NOT NULL CHECK (alert_type IN ('PRICE_SPIKE', 'PRICE_DROP')),
    price_change_pct DECIMAL(10, 4) NOT NULL,
    old_price DECIMAL(20, 8) NOT NULL,
    new_price DECIMAL(20, 8) NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    severity VARCHAR(10) DEFAULT 'LOW',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON price_alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_crypto_time ON price_alerts(crypto_id, created_at DESC);

-- ============================================
-- 5. PROCESSING METADATA TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS processing_metadata (
    id SERIAL PRIMARY KEY,
    topic_name VARCHAR(100) NOT NULL,
    partition_id INTEGER NOT NULL,
    last_offset BIGINT NOT NULL,
    last_timestamp TIMESTAMP NOT NULL,
    consumer_group VARCHAR(100) NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(topic_name, partition_id, consumer_group)
);

-- ============================================
-- 6. VIEWS FOR COMMON QUERIES
-- ============================================

CREATE OR REPLACE VIEW v_latest_prices AS
SELECT
    c.symbol,
    c.name,
    r.price,
    r.volume_24h,
    r.market_cap,
    r.price_change_24h,
    r.timestamp
FROM cryptocurrencies c
INNER JOIN LATERAL (
    SELECT price, volume_24h, market_cap, price_change_24h, timestamp
    FROM raw_price_data
    WHERE crypto_id = c.id
    ORDER BY timestamp DESC
    LIMIT 1
) r ON true
WHERE c.is_active = true;

CREATE OR REPLACE VIEW v_price_stats_24h AS
SELECT
    c.symbol,
    c.name,
    COUNT(*) AS data_points,
    MIN(r.price) AS min_price,
    MAX(r.price) AS max_price,
    AVG(r.price) AS avg_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.price) AS median_price,
    STDDEV(r.price) AS price_stddev
FROM cryptocurrencies c
INNER JOIN raw_price_data r ON c.id = r.crypto_id
WHERE r.timestamp >= NOW() - INTERVAL '24 hours'
  AND c.is_active = true
GROUP BY c.id, c.symbol, c.name;

-- ============================================
-- 7. TIMESCALEDB RETENTION POLICIES
-- ============================================
-- Native retention replaces manual DELETE functions, which bypass TimescaleDB's
-- chunk-drop optimisation and cause full table scans on large datasets.

SELECT add_retention_policy('raw_price_data', INTERVAL '7 days');
SELECT add_retention_policy('price_aggregates_1m', INTERVAL '90 days');

-- ============================================
-- 8. SAMPLE QUERY EXAMPLES (commented)
-- ============================================

-- Get latest price for Bitcoin
-- SELECT * FROM v_latest_prices WHERE symbol = 'BTC';

-- Get 1-minute aggregates for last hour
-- SELECT * FROM price_aggregates_1m
-- WHERE crypto_id = 1
--   AND window_start >= NOW() - INTERVAL '1 hour'
-- ORDER BY window_start DESC;

-- Get price trend (5-minute moving average)
-- SELECT
--     timestamp,
--     price,
--     AVG(price) OVER (
--         ORDER BY timestamp
--         ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
--     ) AS moving_avg_5m
-- FROM raw_price_data
-- WHERE crypto_id = 1
--   AND timestamp >= NOW() - INTERVAL '1 hour'
-- ORDER BY timestamp DESC;

\echo 'Database schema initialized successfully!'
\echo 'Tables: cryptocurrencies, raw_price_data, price_aggregates_1m, price_alerts, processing_metadata'
\echo 'Views: v_latest_prices, v_price_stats_24h'
\echo 'Retention policies: raw_price_data=7d, price_aggregates_1m=90d'
