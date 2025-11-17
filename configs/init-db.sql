-- Real-Time Cryptocurrency Market Analyzer Database Schema
-- Author: Zaid
-- Phase 2, Week 3, Day 3-4

-- Extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Extension for better timestamp handling
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- ============================================
-- 1. CRYPTOCURRENCIES TABLE
-- ============================================
-- Master table for supported cryptocurrencies

CREATE TABLE IF NOT EXISTS cryptocurrencies (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    coingecko_id VARCHAR(50) UNIQUE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial cryptocurrencies (BTC and ETH for Phase 2)
INSERT INTO cryptocurrencies (symbol, name, coingecko_id) VALUES
    ('BTC', 'Bitcoin', 'bitcoin'),
    ('ETH', 'Ethereum', 'ethereum')
ON CONFLICT (symbol) DO NOTHING;

-- ============================================
-- 2. RAW PRICE DATA TABLE
-- ============================================
-- Stores every raw price update from Kafka (high-frequency data)

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

-- Create hypertable for time-series optimization
-- This converts the table to a TimescaleDB hypertable for better performance
SELECT create_hypertable('raw_price_data', 'timestamp', if_not_exists => TRUE);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_raw_price_crypto_id ON raw_price_data(crypto_id);
CREATE INDEX IF NOT EXISTS idx_raw_price_timestamp ON raw_price_data(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_raw_price_crypto_timestamp ON raw_price_data(crypto_id, timestamp DESC);

-- ============================================
-- 3. AGGREGATED PRICE DATA (1-minute windows)
-- ============================================
-- Pre-aggregated data for faster queries

CREATE TABLE IF NOT EXISTS price_aggregates_1m (
    id BIGSERIAL PRIMARY KEY,
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
    UNIQUE(crypto_id, window_start)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_agg_1m_crypto_id ON price_aggregates_1m(crypto_id);
CREATE INDEX IF NOT EXISTS idx_agg_1m_window_start ON price_aggregates_1m(window_start DESC);
CREATE INDEX IF NOT EXISTS idx_agg_1m_crypto_window ON price_aggregates_1m(crypto_id, window_start DESC);

-- ============================================
-- 4. PRICE ALERTS TABLE
-- ============================================
-- Stores anomaly detection alerts from Flink

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

-- Index for efficient querying by time
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON price_alerts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_crypto_time ON price_alerts(crypto_id, created_at DESC);

-- ============================================
-- 5. PROCESSING METADATA TABLE
-- ============================================
-- Tracks Kafka consumer offsets and processing state

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

-- Latest prices for all cryptocurrencies
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

-- Price statistics for last 24 hours
CREATE OR REPLACE VIEW v_price_stats_24h AS
SELECT 
    c.symbol,
    c.name,
    COUNT(*) as data_points,
    MIN(r.price) as min_price,
    MAX(r.price) as max_price,
    AVG(r.price) as avg_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY r.price) as median_price,
    STDDEV(r.price) as price_stddev
FROM cryptocurrencies c
INNER JOIN raw_price_data r ON c.id = r.crypto_id
WHERE r.timestamp >= NOW() - INTERVAL '24 hours'
  AND c.is_active = true
GROUP BY c.id, c.symbol, c.name;

-- ============================================
-- 7. FUNCTIONS FOR DATA CLEANUP
-- ============================================

-- Function to clean old raw data (keep only last 7 days)
CREATE OR REPLACE FUNCTION cleanup_old_raw_data()
RETURNS void AS $$
BEGIN
    DELETE FROM raw_price_data
    WHERE timestamp < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

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
--     ) as moving_avg_5m
-- FROM raw_price_data
-- WHERE crypto_id = 1
--   AND timestamp >= NOW() - INTERVAL '1 hour'
-- ORDER BY timestamp DESC;

-- ============================================
-- COMPLETED!
-- ============================================

\echo 'Database schema initialized successfully!'
\echo 'Tables created: cryptocurrencies, raw_price_data, price_aggregates_1m, price_alerts, processing_metadata'
\echo 'Views created: v_latest_prices, v_price_stats_24h'
\echo 'Ready for Phase 2 Week 4: Data Pipeline Development'
