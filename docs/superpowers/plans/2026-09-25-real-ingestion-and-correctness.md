# Real Ingestion + Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace CoinGecko polling with a real Coinbase trade stream and make every guarantee the README states true. That covers meaningful OHLCV, persisted alerts, a working exactly-once Kafka sink, one symbol list, and a Redis→TimescaleDB fallback.

**Architecture:** An asyncio Python producer publishes validated Coinbase `matches` trades to Kafka `crypto-trades`. The Flink job dedups by `trade_id`, writes raw trades, builds 1-minute OHLCV candles in event time, runs a z-score anomaly detector, and writes to TimescaleDB (idempotent SQL), Redis, and a transactional Kafka alert topic. TimescaleDB continuous aggregates produce the 5m/15m/1h rollups. FastAPI reads the symbol list from the database and falls back to TimescaleDB when Redis misses.

**Tech Stack:** Python 3.12 (websockets 13, pydantic 2, asyncpg, kafka-python-ng, FastAPI, pytest), Java 11 + Flink 1.18.1 (JUnit 5, Flink test harness), TimescaleDB (pg15), Redis 7, Kafka (Confluent 7.5), Next.js 16 / TypeScript / zod.

**Spec:** `docs/superpowers/specs/2026-09-25-real-ingestion-and-correctness-design.md`. Read the "Corrections found while planning" section first; it overrides the sections below it.

## Global Constraints

- Symbols: `BTC, ETH, SOL, XRP, ADA, DOGE, AVAX, POL`. **POL replaces MATIC**, because `MATIC-USD` is delisted on Coinbase. The `cryptocurrencies` table is the only symbol list.
- Coinbase feed: `wss://ws-feed.exchange.coinbase.com`, channel `matches`, public, no auth.
- Kafka input topic `crypto-trades`, 4 partitions, key = symbol. The env var is `KAFKA_TRADES_TOPIC` (not `KAFKA_TOPIC`).
- Kafka alert topic `crypto-alerts`: `EXACTLY_ONCE`, `transactionalIdPrefix("crypto-alerts")`, `transaction.timeout.ms=900000`.
- Checkpoints: 30 s, `EXACTLY_ONCE`, retained on cancellation, set **only in code**. The storage directory comes from `state.checkpoints.dir` on the shared `flink_data` volume.
- Watermarks: bounded out-of-orderness 2 s, idleness 30 s, `allowedLateness(0)`, with late trades going to a side output that is counted.
- Anomaly detector: EWMA α = 2/(60+1), warm-up 30 returns, `trade_count ≥ 5`, `|z| > 4`. Severity: LOW for 4 ≤ |z| < 6, MEDIUM for 6 ≤ |z| < 8, HIGH for |z| ≥ 8. State TTL 1 h. z is clamped to ±9999.
- Renames everywhere: `avg_price→vwap`, `volume_sum→volume`, `event_count→trade_count`, plus a new `quote_volume`.
- All timestamps are `TIMESTAMPTZ`/UTC. Python code uses `datetime.now(timezone.utc)`, never `utcnow()`.
- Java 11 source level. Python ≥ 3.11 (use a 3.12 venv; the system `python3` is 3.14, which the pinned wheels don't support).
- No new frameworks beyond those listed. No migration tool; schema changes require `scripts/teardown.sh`.
- Commit after each task on branch `feat/real-ingestion-correctness`, and end each commit message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Coinbase rejects a product** (the way it would for a delisted pair like MATIC): the producer must exit with a clear error, not reconnect forever. Pinned in Task 3 (`test_subscription_error_is_fatal`).
2. **Redis is down, not just missing a key:** `/api/v1/latest/*` must still serve from PostgreSQL with `X-Data-Source: postgres`, not a 500. Pinned in Task 9 (`test_redis_outage_still_serves_postgres`).
3. **A flat price series makes the variance nearly zero, so z explodes.** An unclamped z would overflow `DECIMAL(10,4)`, fail the JDBC sink, and restart-loop the job. Pinned in Task 6 (`zScoreIsClampedForNearFlatHistory`).
4. **An old `.env` still has `KAFKA_TOPIC=crypto-prices`:** the producer must still publish to `crypto-trades`. Pinned in Task 3 (`test_stale_kafka_topic_env_is_ignored`).
5. **Naive query datetimes** (`?start_time=2026-01-01T00:00:00`) against TIMESTAMPTZ columns must be treated as UTC. Pinned in Task 10 (`test_naive_query_times_are_treated_as_utc`).

---

## File Structure

**Python**
- `src/symbols.py` (new): `Symbol` NamedTuple plus `fetch_symbols(conn)`. Shared by the producer and the API.
- `src/config.py` (rewrite): Kafka, Coinbase and Postgres settings for the producer only.
- `src/producers/coinbase_trades_producer.py` (new): `Trade` model, `parse_match`, `TradeGapTracker`, `CoinbaseTradeProducer`.
- `src/api/registry.py` (new): `symbols_of()`, `require_symbol()`.
- `src/api/database.py`: loads `app.state.symbols`; adds `get_pool`.
- `src/api/models.py`, `src/api/config.py`, `src/api/endpoints/{latest,historical,alerts,symbols,websocket}.py`: modified.
- `scripts/inject_test_alert.py` (new): synthetic TEST trade stream for acceptance check 4.
- Deleted: `src/producers/crypto_price_producer.py`, `src/consumers/`, `src/dashboard/`, `src/utils/`, `requirements-dashboard.txt`.
- Tests: `pytest.ini`, `tests/test_symbols.py`, `tests/producers/test_coinbase_trades_producer.py`, `tests/api/conftest.py`, `tests/api/test_symbols_api.py`, `tests/api/test_latest.py`, `tests/api/test_historical.py`, `tests/api/test_alerts_trending.py`, `tests/sql/schema_checks.sql`.

**Java** (`src/flink_jobs/src/main/java/com/crypto/analyzer/`)
- `models/Trade.java`, `models/Candle.java`, `models/DetectorState.java` (new). `models/PriceAlert.java` (rewrite).
- `functions/CandleAggregator.java`, `functions/CandleWindowFunction.java`, `functions/DedupByTradeId.java`, `functions/ZScoreAnomalyDetector.java`, `functions/LateTradeCounter.java` (new).
- `sinks/JdbcSinks.java` (new). `sinks/RedisSinkFunction.java` (retyped to `Candle`).
- `CryptoPriceAggregator.java` (rewrite).
- Deleted: `models/PriceUpdate.java`, `models/OHLCCandle.java`, `models/OhlcDatabaseRecord.java`, `functions/OHLCAggregator.java`, `functions/OHLCWindowFunction.java`, `functions/AnomalyDetector.java`, `utils/CryptoIdMapper.java`.
- Tests under `src/flink_jobs/src/test/java/com/crypto/analyzer/functions/`.

**Infra and other**
- `configs/init-db.sql` (rewrite), `configs/flink-conf.yaml`, `docker-compose.yml`, `scripts/{start,stop}_pipeline.sh`, `scripts/teardown.sh`, `Makefile`, `requirements*.txt`, `.env.example`.
- `frontend/lib/types.ts`, `frontend/lib/ws.ts`, `frontend/components/ohlc/CandleTable.tsx`.
- `LICENSE`, `frontend/.env.local.example` (new), `README.md` (rewrite of the affected sections).

---

### Task 1: Schema rewrite with a runnable schema check

**Files:**
- Rewrite: `configs/init-db.sql`
- Create: `tests/sql/schema_checks.sql`

**Interfaces:**
- Produces:
  - Tables `cryptocurrencies(id, symbol, name, coingecko_id, coinbase_product, is_active, created_at)`, `raw_trades(crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)` with PK `(crypto_id, trade_id, event_time)`, `price_aggregates_1m(crypto_id, window_start, window_end, open_price, high_price, low_price, close_price, vwap, volume, quote_volume, trade_count, updated_at)` with PK `(crypto_id, window_start)`, and `price_alerts(id, crypto_id, alert_type, severity, z_score, price_change_pct, old_price, new_price, window_start, window_end, created_at)` with UNIQUE `(crypto_id, window_start, alert_type)`.
  - Continuous aggregates `candles_5m`, `candles_15m`, `candles_1h` with columns `crypto_id, bucket, open_price, high_price, low_price, close_price, volume, quote_volume, trade_count, vwap`.

Docker must be running for this task (OrbStack or Docker Desktop).

- [ ] **Step 1: Write the failing schema check**

Create `tests/sql/schema_checks.sql`:

```sql
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
```

- [ ] **Step 2: Run it against the current schema to verify it fails**

```bash
docker run --rm -d --name tsdb-test -e POSTGRES_PASSWORD=test -p 55432:5432 timescale/timescaledb:latest-pg15
sleep 8
docker exec -i tsdb-test psql -U postgres -v ON_ERROR_STOP=1 -q < configs/init-db.sql
docker exec -i tsdb-test psql -U postgres -v ON_ERROR_STOP=1 -q < tests/sql/schema_checks.sql; echo "exit=$?"
docker rm -f tsdb-test
```

Expected: FAIL with `ERROR:  MATIC must be replaced by POL` (or an earlier column error), and `exit=3`.

- [ ] **Step 3: Rewrite `configs/init-db.sql`**

Replace the whole file with:

```sql
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
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_5m WITH (timescaledb.continuous) AS
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

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_15m WITH (timescaledb.continuous) AS
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

CREATE MATERIALIZED VIEW IF NOT EXISTS candles_1h WITH (timescaledb.continuous) AS
SELECT crypto_id,
       time_bucket(INTERVAL '1 hour', window_start) AS bucket,
       first(open_price, window_start)              AS open_price,
       max(high_price)                              AS high_price,
       min(low_price)                               AS low_price,
       last(close_price, window_start)              AS close_price,
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
```

- [ ] **Step 4: Run the check to verify it passes**

Run the same four commands as Step 2.
Expected: the output ends with `schema_checks: ALL PASSED`, followed by `exit=0`.

- [ ] **Step 5: Commit**

```bash
git add configs/init-db.sql tests/sql/schema_checks.sql
git commit -m "feat(db): trade-level schema with continuous-aggregate rollups and idempotent alerts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Python env, test scaffolding, shared symbol loader

**Files:**
- Modify: `requirements.txt`, `requirements-api.txt`
- Create: `pytest.ini`, `src/symbols.py`, `tests/test_symbols.py`

**Interfaces:**
- Produces: `src.symbols.Symbol(symbol: str, name: str, coingecko_id: str, coinbase_product: str)` (a NamedTuple), and `async def fetch_symbols(conn) -> dict[str, Symbol]`. `conn` is anything with an asyncpg-style `async fetch(sql)` (a connection or a pool). It raises `RuntimeError` when there are no active rows.

- [ ] **Step 1: Update requirements and create the venv**

In `requirements.txt`, replace the first line (`kafka-python-ng==2.2.3 ...`) block and the test block so the file contains these additional lines (leave the other existing pins alone until Task 12):

```text
kafka-python-ng==2.2.3           # Python 3.13-compatible Kafka client
websockets==13.1                 # Coinbase WebSocket client (asyncio API)
pydantic==2.10.3                 # Trade validation (shared with the API)
asyncpg==0.30.0                  # Symbol registry reads (shared with the API)
```

and at the bottom:

```text
pytest==8.3.4
pytest-mock==3.14.0
httpx==0.27.2                    # FastAPI TestClient transport
```

In `requirements-api.txt`, delete the `asyncpg==0.30.0` line and the `pydantic==2.10.3` line, because both now come from `requirements.txt`.

```bash
python3.12 -m venv venv
venv/bin/pip install -q -r requirements.txt -r requirements-api.txt
```

Expected: the install finishes without errors.

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 3: Write the failing test**

Create `tests/test_symbols.py`:

```python
import asyncio

import pytest

from src.symbols import Symbol, fetch_symbols


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    async def fetch(self, sql, *args):
        return self.rows


def test_fetch_symbols_keys_by_ticker_in_table_order():
    rows = [
        {"symbol": "BTC", "name": "Bitcoin", "coingecko_id": "bitcoin", "coinbase_product": "BTC-USD"},
        {"symbol": "POL", "name": "Polygon", "coingecko_id": "polygon-ecosystem-token", "coinbase_product": "POL-USD"},
    ]
    symbols = asyncio.run(fetch_symbols(FakeConn(rows)))
    assert list(symbols) == ["BTC", "POL"]
    assert symbols["POL"] == Symbol("POL", "Polygon", "polygon-ecosystem-token", "POL-USD")


def test_fetch_symbols_refuses_empty_table():
    with pytest.raises(RuntimeError, match="init-db.sql"):
        asyncio.run(fetch_symbols(FakeConn([])))
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_symbols.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.symbols'`.

- [ ] **Step 5: Implement `src/symbols.py`**

```python
"""
Tracked-symbol registry.

The cryptocurrencies table is the only list of tracked symbols. The producer
reads it to know which Coinbase products to subscribe to, and the API reads it
to validate symbols and serve /api/v1/symbols.
"""

from typing import NamedTuple


class Symbol(NamedTuple):
    symbol: str
    name: str
    coingecko_id: str
    coinbase_product: str


SYMBOLS_SQL = """
    SELECT symbol, name, coingecko_id, coinbase_product
    FROM cryptocurrencies
    WHERE is_active
    ORDER BY id
"""


async def fetch_symbols(conn) -> dict[str, Symbol]:
    """Return active symbols keyed by ticker, in table order. `conn` may be an asyncpg connection or pool."""
    rows = await conn.fetch(SYMBOLS_SQL)
    if not rows:
        raise RuntimeError(
            "cryptocurrencies has no active symbols; was configs/init-db.sql applied?"
        )
    return {
        r["symbol"]: Symbol(r["symbol"], r["name"], r["coingecko_id"], r["coinbase_product"])
        for r in rows
    }
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_symbols.py -v`
Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt requirements-api.txt pytest.ini src/symbols.py tests/test_symbols.py
git commit -m "feat: shared DB-backed symbol registry and pytest scaffolding

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Coinbase trade producer

**Files:**
- Rewrite: `src/config.py`
- Create: `src/producers/coinbase_trades_producer.py`, `tests/producers/test_coinbase_trades_producer.py`
- Delete: `src/producers/crypto_price_producer.py`, `src/consumers/` (whole directory: `alert_consumer.py` and `__init__.py`)
- Modify: `scripts/start_pipeline.sh`, `scripts/stop_pipeline.sh`, `scripts/teardown.sh`, `Makefile` (the `producer` target plus a new `topics` target), `.env.example`

**Interfaces:**
- Consumes: `src.symbols.Symbol`, `fetch_symbols` (Task 2).
- Produces: Kafka messages on `crypto-trades`, with key = symbol (UTF-8) and value = JSON `{"trade_id": int, "symbol": str, "price": "<decimal string>", "size": "<decimal string>", "side": "buy"|"sell", "sequence": int, "event_time": "YYYY-MM-DDTHH:MM:SS.ffffffZ", "ingest_time": "…Z"}`. Flink's `Trade` (Task 4) parses exactly these names.
- Produces (config): `src.config.KAFKA_PRODUCER_CONFIG: dict`, `KAFKA_TOPIC_TRADES: str`, `COINBASE_WS_URL: str`, `POSTGRES_CONNECT_KWARGS: dict`, `LOG_LEVEL: str`. `scripts/inject_test_alert.py` (Task 13) uses the first two.

- [ ] **Step 1: Write the failing tests**

Create `tests/producers/test_coinbase_trades_producer.py`:

```python
import asyncio
import importlib
import json
from datetime import datetime, timezone

import pytest

from src.producers.coinbase_trades_producer import (
    CoinbaseTradeProducer,
    FatalFeedError,
    TradeGapTracker,
    parse_match,
)
from src.symbols import Symbol

SYMBOLS = {"BTC": Symbol("BTC", "Bitcoin", "bitcoin", "BTC-USD")}
PRODUCTS = {"BTC-USD": "BTC"}
NOW = datetime(2026, 9, 26, 4, 7, 21, tzinfo=timezone.utc)


def match(**overrides) -> dict:
    """A real Coinbase `match` message (captured 2026-09-26)."""
    msg = {
        "type": "match", "trade_id": 1098679010, "maker_order_id": "m", "taker_order_id": "t",
        "side": "buy", "size": "0.00000011", "price": "83982.07", "product_id": "BTC-USD",
        "sequence": 136797320187, "time": "2026-09-26T04:07:20.310372Z",
    }
    msg.update(overrides)
    return msg


class FakeFuture:
    def add_errback(self, fn):
        return self


class FakeKafka:
    def __init__(self):
        self.sent = []

    def send(self, topic, key, value):
        self.sent.append((topic, key, value))
        return FakeFuture()


@pytest.fixture
def producer():
    return CoinbaseTradeProducer(SYMBOLS, FakeKafka(), "crypto-trades")


def test_parse_match_maps_coinbase_fields():
    t = parse_match(match(), PRODUCTS, NOW)
    assert t.symbol == "BTC"
    assert t.trade_id == 1098679010
    assert str(t.price) == "83982.07"
    assert t.side == "buy"
    assert t.event_time == datetime(2026, 9, 26, 4, 7, 20, 310372, tzinfo=timezone.utc)


@pytest.mark.parametrize("bad", [
    {"price": "0"},
    {"size": "-1"},
    {"side": "short"},
    {"trade_id": None},
    {"time": "2026-09-26T04:07:20"},   # no timezone
    {"product_id": "SHIB-USD"},        # not tracked
])
def test_parse_match_rejects_bad_messages(bad):
    with pytest.raises(ValueError):
        parse_match(match(**bad), PRODUCTS, NOW)


def test_trade_json_uses_z_suffix_and_decimal_strings():
    body = json.loads(parse_match(match(), PRODUCTS, NOW).model_dump_json())
    assert body["event_time"] == "2026-09-26T04:07:20.310372Z"
    assert body["ingest_time"] == "2026-09-26T04:07:21.000000Z"
    assert body["price"] == "83982.07"


def test_gap_tracker_counts_missed_trades_and_flags_repeats():
    g = TradeGapTracker()
    assert g.observe("BTC", 10) == 0      # first sighting
    assert g.observe("BTC", 11) == 0
    assert g.observe("BTC", 15) == 3      # 12, 13, 14 missed
    assert g.observe("BTC", 15) is None   # repeat
    assert g.observe("BTC", 12) is None   # older than last seen
    assert g.observe("ETH", 1) == 0       # independent per symbol
    assert g.missed == 3


def test_match_is_published_keyed_by_symbol(producer):
    producer.handle_message(json.dumps(match()))
    topic, key, value = producer.kafka.sent[0]
    assert (topic, key) == ("crypto-trades", "BTC")
    assert json.loads(value)["trade_id"] == 1098679010
    assert producer.stats["published"] == 1


def test_last_match_is_a_trade_and_is_deduped(producer):
    producer.handle_message(json.dumps(match(type="last_match")))
    producer.handle_message(json.dumps(match()))  # same trade_id again, e.g. after a reconnect
    assert len(producer.kafka.sent) == 1
    assert producer.stats["duplicates"] == 1


def test_non_trade_messages_are_ignored(producer):
    producer.handle_message(json.dumps({"type": "subscriptions", "channels": []}))
    producer.handle_message(json.dumps({"type": "heartbeat"}))
    assert producer.kafka.sent == []
    assert producer.stats["invalid"] == 0


def test_invalid_trade_is_counted_not_published(producer):
    producer.handle_message(json.dumps(match(price="abc")))
    producer.handle_message("not json")
    assert producer.kafka.sent == []
    assert producer.stats["invalid"] == 2


def test_subscription_error_is_fatal(producer):
    err = {"type": "error", "message": "Failed to subscribe", "reason": "POL-USD is not a valid product"}
    with pytest.raises(FatalFeedError, match="POL-USD"):
        producer.handle_message(json.dumps(err))


def test_reconnect_backoff_doubles_then_stops_on_fatal(producer):
    outcomes = iter([OSError("reset"), OSError("reset"), FatalFeedError("bad product")])

    async def fake_stream_once():
        raise next(outcomes)

    delays = []

    async def fake_sleep(seconds):
        delays.append(seconds)

    producer.stream_once = fake_stream_once
    producer._sleep = fake_sleep
    with pytest.raises(FatalFeedError):
        asyncio.run(producer.run_forever())
    assert len(delays) == 2
    assert 1.0 <= delays[0] < 2.0   # 1 s + jitter
    assert 2.0 <= delays[1] < 3.0   # doubled
    assert producer.stats["reconnects"] == 2


def test_stale_kafka_topic_env_is_ignored(monkeypatch):
    monkeypatch.setenv("KAFKA_TOPIC", "crypto-prices")
    monkeypatch.delenv("KAFKA_TRADES_TOPIC", raising=False)
    import src.config
    assert importlib.reload(src.config).KAFKA_TOPIC_TRADES == "crypto-trades"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/python -m pytest tests/producers -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.producers.coinbase_trades_producer'`.

- [ ] **Step 3: Rewrite `src/config.py`**

```python
"""
Producer configuration. The API has its own pydantic settings in src/api/config.py.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ============================================
# Kafka
# ============================================
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
# A new variable name on purpose: older .env files set KAFKA_TOPIC=crypto-prices.
KAFKA_TOPIC_TRADES = os.getenv("KAFKA_TRADES_TOPIC", "crypto-trades")

KAFKA_PRODUCER_CONFIG = {
    "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
    "key_serializer": lambda k: k.encode("utf-8"),
    "value_serializer": lambda v: v.encode("utf-8"),
    "acks": "all",
    "retries": 5,
    # One in-flight request keeps per-partition order even when a send is retried.
    # A retry duplicate therefore lands right after the original, which is what
    # lets Flink's DedupByTradeId drop it with a single last-seen trade_id per symbol.
    "max_in_flight_requests_per_connection": 1,
    "linger_ms": 20,
    "compression_type": "gzip",
}

# ============================================
# Coinbase Exchange public market data
# ============================================
COINBASE_WS_URL = os.getenv("COINBASE_WS_URL", "wss://ws-feed.exchange.coinbase.com")

# ============================================
# PostgreSQL (symbol registry)
# ============================================
POSTGRES_CONNECT_KWARGS = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5433")),
    "database": os.getenv("POSTGRES_DB", "crypto_db"),
    "user": os.getenv("POSTGRES_USER", "crypto_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "crypto_pass"),
}

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

- [ ] **Step 4: Implement `src/producers/coinbase_trades_producer.py`**

```python
"""
Coinbase trade producer.

Streams every trade for the tracked products from Coinbase Exchange's public
`matches` WebSocket channel and publishes one Kafka message per trade to
`crypto-trades`, keyed by symbol.

Completeness: Coinbase trade_ids are contiguous per product, so a jump in
trade_id is a count of trades we never received (for example during a
reconnect). `sequence` is NOT contiguous on this channel (it is shared with
order-book events), so it is stored but not used for gap detection.
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

import asyncpg
from kafka import KafkaProducer
from pydantic import AwareDatetime, BaseModel, Field, field_serializer
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from src.config import (
    COINBASE_WS_URL,
    KAFKA_PRODUCER_CONFIG,
    KAFKA_TOPIC_TRADES,
    LOG_LEVEL,
    POSTGRES_CONNECT_KWARGS,
)
from src.symbols import Symbol, fetch_symbols

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

HEALTHY_CONNECTION_SECONDS = 60   # a connection that lived this long resets the backoff
MAX_BACKOFF_SECONDS = 30.0
STATS_LOG_INTERVAL_SECONDS = 60


class Trade(BaseModel):
    trade_id: int = Field(gt=0)
    symbol: str
    price: Decimal = Field(gt=0)
    size: Decimal = Field(gt=0)
    side: Literal["buy", "sell"]
    sequence: int
    event_time: AwareDatetime
    ingest_time: AwareDatetime

    @field_serializer("event_time", "ingest_time")
    def _utc_z(self, dt: datetime) -> str:
        # Flink's Jackson Instant parser (Java 11 ISO_INSTANT) wants a trailing Z, not +00:00.
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class FatalFeedError(Exception):
    """Coinbase rejected the subscription (e.g. a delisted product). Reconnecting will not help."""


def parse_match(msg: dict, symbol_by_product: dict[str, str], ingest_time: datetime) -> Trade:
    """Map a Coinbase `match`/`last_match` message to a Trade. Raises ValueError if it is malformed."""
    symbol = symbol_by_product.get(msg.get("product_id"))
    if symbol is None:
        raise ValueError(f"untracked product: {msg.get('product_id')}")
    return Trade(
        trade_id=msg.get("trade_id"),
        symbol=symbol,
        price=msg.get("price"),
        size=msg.get("size"),
        side=msg.get("side"),
        sequence=msg.get("sequence"),
        event_time=msg.get("time"),
        ingest_time=ingest_time,
    )


class TradeGapTracker:
    """Counts trades missed per symbol from contiguous Coinbase trade_ids."""

    def __init__(self):
        self.last_trade_id: dict[str, int] = {}
        self.missed = 0

    def observe(self, symbol: str, trade_id: int) -> Optional[int]:
        """Record a trade_id. Returns None if it is not newer than the last one seen
        (a repeat or replay), otherwise the number of trades skipped since the previous one."""
        last = self.last_trade_id.get(symbol)
        if last is not None and trade_id <= last:
            return None
        self.last_trade_id[symbol] = trade_id
        if last is None:
            return 0
        gap = trade_id - last - 1
        self.missed += gap
        return gap


class CoinbaseTradeProducer:
    def __init__(self, symbols: dict[str, Symbol], kafka_producer, topic: str, ws_url: str = COINBASE_WS_URL):
        self.symbol_by_product = {s.coinbase_product: s.symbol for s in symbols.values()}
        self.kafka = kafka_producer
        self.topic = topic
        self.ws_url = ws_url
        self.gaps = TradeGapTracker()
        self.stats = {"published": 0, "invalid": 0, "duplicates": 0, "send_errors": 0, "reconnects": 0}
        self._sleep = asyncio.sleep
        self._last_stats_log = time.monotonic()

    def handle_message(self, raw: str) -> None:
        """Validate one WebSocket frame and publish it if it is a new trade."""
        try:
            msg = json.loads(raw)
        except ValueError:
            self.stats["invalid"] += 1
            logger.warning("Dropping non-JSON frame: %.200s", raw)
            return

        kind = msg.get("type")
        if kind == "error":
            raise FatalFeedError(f"{msg.get('message')}: {msg.get('reason', '')}")
        if kind not in ("match", "last_match"):
            return

        try:
            trade = parse_match(msg, self.symbol_by_product, datetime.now(timezone.utc))
        except ValueError as e:
            self.stats["invalid"] += 1
            logger.warning("Dropping invalid trade message: %s", e)
            return

        gap = self.gaps.observe(trade.symbol, trade.trade_id)
        if gap is None:
            self.stats["duplicates"] += 1
            return
        if gap:
            logger.warning("%s: %d trades missed before trade_id %d", trade.symbol, gap, trade.trade_id)

        # ponytail: KafkaProducer.send can block the event loop briefly on first metadata fetch
        # or a full buffer; fine at ~10 trades/s, move to aiokafka if throughput grows 100x.
        self.kafka.send(self.topic, key=trade.symbol, value=trade.model_dump_json()).add_errback(
            self._on_send_error
        )
        self.stats["published"] += 1

    def _on_send_error(self, exc) -> None:
        self.stats["send_errors"] += 1
        logger.error("Kafka send failed: %s", exc)

    def _maybe_log_stats(self) -> None:
        now = time.monotonic()
        if now - self._last_stats_log >= STATS_LOG_INTERVAL_SECONDS:
            self._last_stats_log = now
            logger.info("stats %s missed_trades=%d", self.stats, self.gaps.missed)

    async def stream_once(self) -> None:
        """Connect, subscribe, and publish trades until the connection drops."""
        async with connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": sorted(self.symbol_by_product),
                "channels": ["matches"],
            }))
            logger.info("Subscribed to %d products on %s", len(self.symbol_by_product), self.ws_url)
            async for raw in ws:
                self.handle_message(raw)
                self._maybe_log_stats()

    async def run_forever(self) -> None:
        """Stream until a FatalFeedError; otherwise reconnect with capped exponential backoff plus jitter."""
        backoff = 1.0
        while True:
            started = time.monotonic()
            try:
                await self.stream_once()
                logger.warning("Coinbase closed the WebSocket")
            except (OSError, WebSocketException) as e:
                logger.warning("WebSocket error: %s", e)
            if time.monotonic() - started > HEALTHY_CONNECTION_SECONDS:
                backoff = 1.0
            self.stats["reconnects"] += 1
            await self._sleep(backoff + random.random())
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)


async def amain() -> None:
    conn = await asyncpg.connect(**POSTGRES_CONNECT_KWARGS)
    try:
        symbols = await fetch_symbols(conn)
    finally:
        await conn.close()

    kafka = KafkaProducer(**KAFKA_PRODUCER_CONFIG)
    producer = CoinbaseTradeProducer(symbols, kafka, KAFKA_TOPIC_TRADES)
    try:
        await producer.run_forever()
    finally:
        kafka.flush(timeout=10)
        kafka.close()
        logger.info("Shutdown stats %s missed_trades=%d", producer.stats, producer.gaps.missed)


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        logger.info("Stopped by user")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/bin/python -m pytest tests/producers -v`
Expected: all pass (16 tests, including the 6 parametrized cases).

- [ ] **Step 6: Delete the old producer and the alert printer**

```bash
git rm -q src/producers/crypto_price_producer.py
git rm -rq src/consumers
```

- [ ] **Step 7: Wire up scripts, Makefile and `.env.example`**

`scripts/start_pipeline.sh`: directly after the `echo "  Kafka ready."` line, insert:

```bash
echo "Ensuring topic crypto-trades (4 partitions, one per Flink subtask)..."
docker-compose exec -T kafka kafka-topics --bootstrap-server localhost:9092 \
    --create --if-not-exists --topic crypto-trades --partitions 4 --replication-factor 1
```

In the same file, replace:

```bash
echo "Starting crypto price producer..."
python3 -m src.producers.crypto_price_producer &
```

with:

```bash
echo "Starting Coinbase trade producer..."
venv/bin/python -m src.producers.coinbase_trades_producer &
```

In `scripts/stop_pipeline.sh` and `scripts/teardown.sh`, replace every `src.producers.crypto_price_producer` with `src.producers.coinbase_trades_producer`.

In `Makefile`, replace the `producer:` target (the 3 recipe lines) with:

```make
topics: ## Create Kafka topics (idempotent)
	docker exec kafka kafka-topics --bootstrap-server localhost:9092 \
		--create --if-not-exists --topic crypto-trades --partitions 4 --replication-factor 1

producer: topics ## Run the Coinbase trade producer
	@echo "Starting Coinbase trade producer..."
	PYTHONPATH=. $(PYTHON) -m src.producers.coinbase_trades_producer
```

and add `topics` to the `.PHONY` list.

In `.env.example`, replace the `KAFKA_TOPIC=crypto-prices` line with `KAFKA_TRADES_TOPIC=crypto-trades`, and replace the whole `# CoinGecko API ...` block (the header and its 3 comment lines) with:

```text
# ============================================
# Coinbase Exchange (public market data, no key needed)
# ============================================
# COINBASE_WS_URL=wss://ws-feed.exchange.coinbase.com
```

- [ ] **Step 8: Verify nothing still references the old producer**

Run: `grep -rnE 'crypto_price_producer|crypto-prices|alert_consumer|CRYPTO_IDS' src scripts Makefile .env.example docker-compose.yml`
Expected: only the two `docker-compose.yml` comments mentioning `crypto-prices`, which Task 7 fixes.

- [ ] **Step 9: Commit**

```bash
git add -A src/config.py src/producers tests/producers scripts Makefile .env.example
git commit -m "feat(producer): stream Coinbase trades with validation, gap tracking and reconnect backoff

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Flink `Trade`/`Candle` models and the OHLCV aggregator

New classes sit alongside the old ones so the job still compiles. Task 7 switches the job over and deletes the old classes.

**Files:**
- Modify: `src/flink_jobs/pom.xml` (test dependencies, surefire)
- Create: `src/flink_jobs/src/main/java/com/crypto/analyzer/models/Trade.java`, `.../models/Candle.java`, `.../functions/CandleAggregator.java`
- Test: `src/flink_jobs/src/test/java/com/crypto/analyzer/functions/CandleAggregatorTest.java`

**Interfaces:**
- Consumes: the Kafka JSON from Task 3.
- Produces:
  - `Trade` with public fields `long tradeId; String symbol; BigDecimal price, size; String side; long sequence; Instant eventTime, ingestTime`; methods `String getSymbol()`, `long getEventTimeMillis()`, `boolean isValid()`; constructors `Trade()` and `Trade(long tradeId, String symbol, BigDecimal price, BigDecimal size, String side, long sequence, Instant eventTime, Instant ingestTime)`.
  - `Candle` with public fields `String symbol; Instant windowStart, windowEnd; BigDecimal open, high, low, close, vwap, volume, quoteVolume; int tradeCount`, plus `String getSymbol()`. Its Jackson JSON (the Redis value) has keys `symbol, windowStart, windowEnd, open, high, low, close, vwap, volume, quoteVolume, tradeCount`.
  - `CandleAggregator implements AggregateFunction<Trade, CandleAggregator.Accumulator, Candle>`.

- [ ] **Step 1: Add the test dependencies to `pom.xml`**

Inside `<dependencies>`, after the existing `flink-test-utils` dependency, add:

```xml
        <!-- Operator test harnesses (KeyedOneInputStreamOperatorTestHarness) -->
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-streaming-java</artifactId>
            <version>${flink.version}</version>
            <type>test-jar</type>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.apache.flink</groupId>
            <artifactId>flink-runtime</artifactId>
            <version>${flink.version}</version>
            <type>test-jar</type>
            <scope>test</scope>
        </dependency>
```

Inside `<plugins>`, after the compiler plugin, add:

```xml
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.2.5</version>
            </plugin>
```

- [ ] **Step 2: Write the failing test**

Create `src/flink_jobs/src/test/java/com/crypto/analyzer/functions/CandleAggregatorTest.java`:

```java
package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.Trade;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;

import static org.junit.jupiter.api.Assertions.assertEquals;

class CandleAggregatorTest {

    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");
    private final CandleAggregator agg = new CandleAggregator();

    private static Trade trade(long id, String price, String size, long offsetMs) {
        Instant t = T0.plusMillis(offsetMs);
        return new Trade(id, "BTC", new BigDecimal(price), new BigDecimal(size), "buy", id * 10, t, t.plusMillis(50));
    }

    private CandleAggregator.Accumulator accumulate(Trade... trades) {
        CandleAggregator.Accumulator acc = agg.createAccumulator();
        for (Trade t : trades) {
            acc = agg.add(t, acc);
        }
        return acc;
    }

    private static void assertSameValue(String expected, BigDecimal actual) {
        assertEquals(0, new BigDecimal(expected).compareTo(actual), "expected " + expected + " but was " + actual);
    }

    @Test
    void openAndCloseFollowEventTimeNotArrivalOrder() {
        Candle c = agg.getResult(accumulate(
                trade(2, "101", "1", 2000),
                trade(3, "103", "1", 3000),
                trade(1, "100", "1", 1000)));
        assertSameValue("100", c.open);
        assertSameValue("103", c.close);
        assertSameValue("103", c.high);
        assertSameValue("100", c.low);
        assertEquals(3, c.tradeCount);
        assertEquals("BTC", c.symbol);
    }

    @Test
    void sameTimestampTiesBreakOnTradeId() {
        Candle c = agg.getResult(accumulate(trade(8, "50", "1", 1000), trade(7, "49", "1", 1000)));
        assertSameValue("49", c.open);
        assertSameValue("50", c.close);
    }

    @Test
    void vwapIsQuoteVolumeOverVolume() {
        // 100*1 + 110*3 = 430 quote over 4 base -> vwap 107.5
        Candle c = agg.getResult(accumulate(trade(1, "100", "1", 0), trade(2, "110", "3", 10)));
        assertSameValue("4", c.volume);
        assertSameValue("430", c.quoteVolume);
        assertSameValue("107.5", c.vwap);
    }

    @Test
    void mergeMatchesSinglePassAggregation() {
        Trade[] all = {
                trade(1, "100", "1", 1000), trade(2, "98", "2", 2000), trade(3, "105", "1", 3000),
                trade(4, "101", "4", 4000), trade(5, "99", "1", 5000)};
        Candle single = agg.getResult(accumulate(all));
        Candle merged = agg.getResult(agg.merge(
                accumulate(all[0], all[3]),
                accumulate(all[1], all[2], all[4])));
        assertSameValue(single.open.toPlainString(), merged.open);
        assertSameValue(single.high.toPlainString(), merged.high);
        assertSameValue(single.low.toPlainString(), merged.low);
        assertSameValue(single.close.toPlainString(), merged.close);
        assertSameValue(single.volume.toPlainString(), merged.volume);
        assertSameValue(single.vwap.toPlainString(), merged.vwap);
        assertEquals(single.tradeCount, merged.tradeCount);
    }

    @Test
    void mergeWithEmptyAccumulatorKeepsTheOtherSide() {
        CandleAggregator.Accumulator filled = accumulate(trade(1, "100", "1", 0));
        Candle c = agg.getResult(agg.merge(agg.createAccumulator(), filled));
        assertSameValue("100", c.open);
        assertEquals(1, c.tradeCount);
    }
}
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `mvn -q -f src/flink_jobs/pom.xml test -Dtest=CandleAggregatorTest`
Expected: FAIL with compilation errors: `cannot find symbol: class CandleAggregator` / `class Trade` / `class Candle`.

- [ ] **Step 4: Create `models/Trade.java`**

```java
package com.crypto.analyzer.models;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * One Coinbase trade as published by src/producers/coinbase_trades_producer.py.
 *
 * <p>Public fields plus a no-arg constructor keep this a Flink POJO (efficient state serialization).
 */
@JsonIgnoreProperties(ignoreUnknown = true)
public class Trade implements Serializable {

    private static final long serialVersionUID = 1L;

    @JsonProperty("trade_id")    public long tradeId;
    @JsonProperty("symbol")      public String symbol;
    @JsonProperty("price")       public BigDecimal price;
    @JsonProperty("size")        public BigDecimal size;
    @JsonProperty("side")        public String side;
    @JsonProperty("sequence")    public long sequence;
    @JsonProperty("event_time")  public Instant eventTime;
    @JsonProperty("ingest_time") public Instant ingestTime;

    public Trade() {}

    public Trade(long tradeId, String symbol, BigDecimal price, BigDecimal size, String side,
                 long sequence, Instant eventTime, Instant ingestTime) {
        this.tradeId = tradeId;
        this.symbol = symbol;
        this.price = price;
        this.size = size;
        this.side = side;
        this.sequence = sequence;
        this.eventTime = eventTime;
        this.ingestTime = ingestTime;
    }

    public String getSymbol() {
        return symbol;
    }

    public long getEventTimeMillis() {
        return eventTime.toEpochMilli();
    }

    public boolean isValid() {
        return tradeId > 0 && symbol != null && eventTime != null && ingestTime != null
                && price != null && price.signum() > 0
                && size != null && size.signum() > 0;
    }
}
```

- [ ] **Step 5: Create `models/Candle.java`**

```java
package com.crypto.analyzer.models;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;

/**
 * One 1-minute OHLCV candle built from real trades.
 *
 * <p>Public fields keep this a Flink POJO and define the Redis JSON shape read by the API:
 * symbol, windowStart, windowEnd (epoch seconds), open, high, low, close, vwap, volume,
 * quoteVolume, tradeCount.
 */
public class Candle implements Serializable {

    private static final long serialVersionUID = 1L;

    public String symbol;
    public Instant windowStart;
    public Instant windowEnd;
    public BigDecimal open;
    public BigDecimal high;
    public BigDecimal low;
    public BigDecimal close;
    /** Volume-weighted average price: quoteVolume / volume. */
    public BigDecimal vwap;
    /** Base-asset units traded, e.g. BTC. */
    public BigDecimal volume;
    /** Quote currency (USD) traded: sum of price * size. */
    public BigDecimal quoteVolume;
    public int tradeCount;

    public Candle() {}

    public String getSymbol() {
        return symbol;
    }
}
```

- [ ] **Step 6: Create `functions/CandleAggregator.java`**

```java
package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.Trade;
import org.apache.flink.api.common.functions.AggregateFunction;

import java.io.Serializable;
import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * Builds an OHLCV candle from trades.
 *
 * <p>Open and close are the trades with the earliest and latest (event_time, trade_id), so
 * out-of-order arrival inside a window does not change the candle.
 */
public class CandleAggregator implements AggregateFunction<Trade, CandleAggregator.Accumulator, Candle> {

    private static final long serialVersionUID = 1L;

    public static class Accumulator implements Serializable {
        private static final long serialVersionUID = 1L;
        public String symbol;
        public BigDecimal open;
        public BigDecimal high;
        public BigDecimal low;
        public BigDecimal close;
        public long openTime = Long.MAX_VALUE;
        public long openTradeId = Long.MAX_VALUE;
        public long closeTime = Long.MIN_VALUE;
        public long closeTradeId = Long.MIN_VALUE;
        public BigDecimal volume = BigDecimal.ZERO;
        public BigDecimal quoteVolume = BigDecimal.ZERO;
        public int tradeCount;
    }

    @Override
    public Accumulator createAccumulator() {
        return new Accumulator();
    }

    @Override
    public Accumulator add(Trade t, Accumulator acc) {
        long ts = t.getEventTimeMillis();
        acc.symbol = t.symbol;
        if (isBefore(ts, t.tradeId, acc.openTime, acc.openTradeId)) {
            acc.open = t.price;
            acc.openTime = ts;
            acc.openTradeId = t.tradeId;
        }
        if (isBefore(acc.closeTime, acc.closeTradeId, ts, t.tradeId)) {
            acc.close = t.price;
            acc.closeTime = ts;
            acc.closeTradeId = t.tradeId;
        }
        acc.high = acc.high == null ? t.price : acc.high.max(t.price);
        acc.low = acc.low == null ? t.price : acc.low.min(t.price);
        acc.volume = acc.volume.add(t.size);
        acc.quoteVolume = acc.quoteVolume.add(t.price.multiply(t.size));
        acc.tradeCount++;
        return acc;
    }

    @Override
    public Candle getResult(Accumulator acc) {
        Candle c = new Candle();
        c.symbol = acc.symbol;
        c.open = acc.open;
        c.high = acc.high;
        c.low = acc.low;
        c.close = acc.close;
        c.volume = acc.volume;
        c.quoteVolume = acc.quoteVolume;
        c.tradeCount = acc.tradeCount;
        c.vwap = acc.volume.signum() > 0
                ? acc.quoteVolume.divide(acc.volume, 8, RoundingMode.HALF_EVEN)
                : acc.close;
        return c;
    }

    @Override
    public Accumulator merge(Accumulator a, Accumulator b) {
        if (b.tradeCount == 0) {
            return a;
        }
        if (a.tradeCount == 0) {
            return b;
        }
        Accumulator m = new Accumulator();
        m.symbol = a.symbol;

        Accumulator first = isBefore(a.openTime, a.openTradeId, b.openTime, b.openTradeId) ? a : b;
        m.open = first.open;
        m.openTime = first.openTime;
        m.openTradeId = first.openTradeId;

        Accumulator last = isBefore(a.closeTime, a.closeTradeId, b.closeTime, b.closeTradeId) ? b : a;
        m.close = last.close;
        m.closeTime = last.closeTime;
        m.closeTradeId = last.closeTradeId;

        m.high = a.high.max(b.high);
        m.low = a.low.min(b.low);
        m.volume = a.volume.add(b.volume);
        m.quoteVolume = a.quoteVolume.add(b.quoteVolume);
        m.tradeCount = a.tradeCount + b.tradeCount;
        return m;
    }

    /** True if (t1, id1) sorts strictly before (t2, id2). */
    static boolean isBefore(long t1, long id1, long t2, long id2) {
        return t1 < t2 || (t1 == t2 && id1 < id2);
    }
}
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `mvn -q -f src/flink_jobs/pom.xml test -Dtest=CandleAggregatorTest`
Expected: `Tests run: 5, Failures: 0, Errors: 0` (on `-q` success, no output and exit code 0).

- [ ] **Step 8: Commit**

```bash
git add src/flink_jobs/pom.xml src/flink_jobs/src
git commit -m "feat(flink): trade model and event-time OHLCV aggregator with VWAP

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `DedupByTradeId`

**Files:**
- Create: `src/flink_jobs/src/main/java/com/crypto/analyzer/functions/DedupByTradeId.java`
- Test: `src/flink_jobs/src/test/java/com/crypto/analyzer/functions/DedupByTradeIdTest.java`

**Interfaces:**
- Consumes: `Trade` (Task 4).
- Produces: `DedupByTradeId extends KeyedProcessFunction<String, Trade, Trade>`, with metric `duplicateTrades`.

- [ ] **Step 1: Write the failing test**

```java
package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Trade;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.streaming.api.operators.KeyedProcessOperator;
import org.apache.flink.streaming.util.KeyedOneInputStreamOperatorTestHarness;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DedupByTradeIdTest {

    private KeyedOneInputStreamOperatorTestHarness<String, Trade, Trade> harness;

    @BeforeEach
    void setUp() throws Exception {
        harness = new KeyedOneInputStreamOperatorTestHarness<>(
                new KeyedProcessOperator<>(new DedupByTradeId()), Trade::getSymbol, Types.STRING);
        harness.open();
    }

    @AfterEach
    void tearDown() throws Exception {
        harness.close();
    }

    private static Trade trade(String symbol, long id) {
        Instant t = Instant.parse("2026-01-01T00:00:00Z").plusSeconds(id);
        return new Trade(id, symbol, BigDecimal.TEN, BigDecimal.ONE, "buy", id, t, t);
    }

    @Test
    void dropsRepeatsAndOlderIdsPerSymbol() throws Exception {
        harness.processElement(trade("BTC", 1), 0);
        harness.processElement(trade("BTC", 2), 0);
        harness.processElement(trade("BTC", 2), 0);   // Kafka retry duplicate
        harness.processElement(trade("BTC", 1), 0);   // older than last seen
        harness.processElement(trade("ETH", 1), 0);   // other symbol has its own state
        harness.processElement(trade("BTC", 3), 0);

        List<String> out = harness.extractOutputValues().stream()
                .map(t -> t.symbol + ":" + t.tradeId)
                .collect(Collectors.toList());
        assertEquals(List.of("BTC:1", "BTC:2", "ETH:1", "BTC:3"), out);
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `mvn -q -f src/flink_jobs/pom.xml test -Dtest=DedupByTradeIdTest`
Expected: FAIL with `cannot find symbol: class DedupByTradeId`.

- [ ] **Step 3: Implement `DedupByTradeId.java`**

```java
package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Trade;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.metrics.Counter;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;

/**
 * Drops trades whose trade_id is not newer than the last one seen for the symbol.
 *
 * <p>Coinbase trade_ids are contiguous per product and the producer keeps per-partition order
 * (one in-flight request), so a Kafka retry duplicate always arrives right after its original.
 * One Long of keyed state is enough to remove it, and it is checkpointed with the source offsets,
 * so the guarantee survives restarts.
 */
public class DedupByTradeId extends KeyedProcessFunction<String, Trade, Trade> {

    private static final long serialVersionUID = 1L;

    private transient ValueState<Long> lastTradeId;
    private transient Counter duplicates;

    @Override
    public void open(Configuration parameters) {
        lastTradeId = getRuntimeContext().getState(new ValueStateDescriptor<>("last-trade-id", Types.LONG));
        duplicates = getRuntimeContext().getMetricGroup().counter("duplicateTrades");
    }

    @Override
    public void processElement(Trade trade, Context ctx, Collector<Trade> out) throws Exception {
        Long last = lastTradeId.value();
        if (last != null && trade.tradeId <= last) {
            duplicates.inc();
            return;
        }
        lastTradeId.update(trade.tradeId);
        out.collect(trade);
    }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `mvn -q -f src/flink_jobs/pom.xml test -Dtest=DedupByTradeIdTest`
Expected: exit code 0.

- [ ] **Step 5: Commit**

```bash
git add src/flink_jobs/src
git commit -m "feat(flink): dedup trades by last-seen trade_id per symbol

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Z-score anomaly detector and the alert model

**Files:**
- Create: `src/flink_jobs/src/main/java/com/crypto/analyzer/models/DetectorState.java`, `.../functions/ZScoreAnomalyDetector.java`
- Rewrite: `.../models/PriceAlert.java`
- Modify: `.../CryptoPriceAggregator.java` (2 lines in `PriceAlertSerializer`)
- Test: `src/flink_jobs/src/test/java/com/crypto/analyzer/functions/ZScoreAnomalyDetectorTest.java`

**Interfaces:**
- Consumes: `Candle` (Task 4).
- Produces:
  - `PriceAlert` with public fields `symbol, alertType, severity (String), zScore (double), priceChangePercent, oldPrice, newPrice (BigDecimal), windowStart, windowEnd, timestamp (String ISO-8601)`, plus `static PriceAlert fromZScore(Candle candle, BigDecimal prevClose, double z)` and `static String severityFor(double absZ)`. JSON keys: `symbol, alert_type, severity, z_score, price_change_percent, old_price, new_price, window_start, window_end, timestamp`.
  - `ZScoreAnomalyDetector extends KeyedProcessFunction<String, Candle, PriceAlert>`.

- [ ] **Step 1: Write the failing test**

```java
package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.PriceAlert;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.streaming.api.operators.KeyedProcessOperator;
import org.apache.flink.streaming.util.KeyedOneInputStreamOperatorTestHarness;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ZScoreAnomalyDetectorTest {

    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");

    private KeyedOneInputStreamOperatorTestHarness<String, Candle, PriceAlert> harness;
    private BigDecimal lastClose;
    private int minute;

    @BeforeEach
    void setUp() throws Exception {
        harness = new KeyedOneInputStreamOperatorTestHarness<>(
                new KeyedProcessOperator<>(new ZScoreAnomalyDetector()), Candle::getSymbol, Types.STRING);
        harness.open();
        lastClose = new BigDecimal("100");
        minute = 0;
    }

    @AfterEach
    void tearDown() throws Exception {
        harness.close();
    }

    /** Feed the next 1-minute candle, whose close is lastClose * exp(logReturn). */
    private void feed(double logReturn, int trades) throws Exception {
        BigDecimal close = lastClose.multiply(BigDecimal.valueOf(Math.exp(logReturn)))
                .setScale(8, RoundingMode.HALF_EVEN);
        Candle c = new Candle();
        c.symbol = "BTC";
        c.windowStart = T0.plusSeconds(60L * minute);
        c.windowEnd = c.windowStart.plusSeconds(60);
        c.open = lastClose;
        c.high = close.max(lastClose);
        c.low = close.min(lastClose);
        c.close = close;
        c.vwap = close;
        c.volume = BigDecimal.ONE;
        c.quoteVolume = close;
        c.tradeCount = trades;
        harness.processElement(c, c.windowEnd.toEpochMilli() - 1);
        lastClose = close;
        minute++;
    }

    /** One anchoring candle, then n calm returns alternating +/-step. */
    private void warmUp(int n, double step) throws Exception {
        feed(0, 10);
        for (int i = 0; i < n; i++) {
            feed(i % 2 == 0 ? step : -step, 10);
        }
    }

    private List<PriceAlert> alerts() {
        return harness.extractOutputValues();
    }

    @Test
    void noAlertDuringWarmUp() throws Exception {
        warmUp(10, 0.001);
        feed(0.05, 10);
        assertTrue(alerts().isEmpty());
    }

    @Test
    void largeRiseAfterWarmUpIsHighSeveritySpike() throws Exception {
        warmUp(40, 0.001);
        BigDecimal before = lastClose;
        feed(0.05, 10);
        List<PriceAlert> out = alerts();
        assertEquals(1, out.size());
        PriceAlert a = out.get(0);
        assertEquals("PRICE_SPIKE", a.alertType);
        assertEquals("HIGH", a.severity);
        assertTrue(a.zScore > 8, "z was " + a.zScore);
        assertEquals(0, before.compareTo(a.oldPrice));
        assertEquals(0, lastClose.compareTo(a.newPrice));
        assertEquals(T0.plusSeconds(60L * 41).toString(), a.windowStart);
    }

    @Test
    void largeFallIsPriceDrop() throws Exception {
        warmUp(40, 0.001);
        feed(-0.05, 10);
        assertEquals(1, alerts().size());
        assertEquals("PRICE_DROP", alerts().get(0).alertType);
        assertTrue(alerts().get(0).zScore < -8);
    }

    @Test
    void calmMoveDoesNotAlert() throws Exception {
        warmUp(40, 0.001);
        feed(0.001, 10);
        assertTrue(alerts().isEmpty());
    }

    @Test
    void thinCandleIsIgnored() throws Exception {
        warmUp(40, 0.001);
        feed(0.05, 3);
        assertTrue(alerts().isEmpty());
    }

    @Test
    void gapInMinutesReanchorsWithoutScoring() throws Exception {
        warmUp(40, 0.001);
        minute += 5;              // five quiet minutes with no candle
        feed(0.05, 10);
        assertTrue(alerts().isEmpty());
    }

    @Test
    void zScoreIsClampedForNearFlatHistory() throws Exception {
        warmUp(40, 1e-9);
        feed(0.05, 10);
        assertEquals(1, alerts().size());
        assertEquals(ZScoreAnomalyDetector.Z_CLAMP, alerts().get(0).zScore);
    }

    @Test
    void severityBands() {
        assertEquals("LOW", PriceAlert.severityFor(4.01));
        assertEquals("LOW", PriceAlert.severityFor(5.99));
        assertEquals("MEDIUM", PriceAlert.severityFor(6.0));
        assertEquals("HIGH", PriceAlert.severityFor(8.0));
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `mvn -q -f src/flink_jobs/pom.xml test -Dtest=ZScoreAnomalyDetectorTest`
Expected: FAIL with `cannot find symbol: class ZScoreAnomalyDetector`.

- [ ] **Step 3: Create `models/DetectorState.java`**

```java
package com.crypto.analyzer.models;

import java.math.BigDecimal;

/**
 * Per-symbol state of the z-score detector: an exponentially weighted mean and variance
 * of 1-minute log returns, plus the previous candle it scores against.
 * Public fields keep it a Flink POJO so it checkpoints efficiently.
 */
public class DetectorState {

    /** EWMA smoothing for a ~60-candle span. */
    public static final double ALPHA = 2.0 / (60 + 1);

    public double mean;
    public double variance;
    public int returnsSeen;
    public long prevWindowStartMs;
    public BigDecimal prevClose;

    public DetectorState() {}

    /** z-score of r against the history so far, or NaN when there is no spread yet. */
    public double zScore(double r) {
        return variance > 0 ? (r - mean) / Math.sqrt(variance) : Double.NaN;
    }

    /** Fold r into the EWMA mean and variance (incremental form). */
    public void update(double r) {
        double diff = r - mean;
        double incr = ALPHA * diff;
        mean += incr;
        variance = (1 - ALPHA) * (variance + diff * incr);
        returnsSeen++;
    }
}
```

- [ ] **Step 4: Rewrite `models/PriceAlert.java`**

```java
package com.crypto.analyzer.models;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.io.Serializable;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;

/**
 * An anomaly alert: a 1-minute log return whose z-score against the symbol's recent
 * history exceeded the detector threshold. Written to price_alerts and to Kafka crypto-alerts.
 */
public class PriceAlert implements Serializable {

    private static final long serialVersionUID = 2L;
    private static final BigDecimal HUNDRED = new BigDecimal("100");

    @JsonProperty("symbol")               public String symbol;
    @JsonProperty("alert_type")           public String alertType;   // PRICE_SPIKE | PRICE_DROP
    @JsonProperty("severity")             public String severity;    // LOW | MEDIUM | HIGH
    @JsonProperty("z_score")              public double zScore;
    @JsonProperty("price_change_percent") public BigDecimal priceChangePercent;
    @JsonProperty("old_price")            public BigDecimal oldPrice;   // previous candle close
    @JsonProperty("new_price")            public BigDecimal newPrice;   // this candle close
    @JsonProperty("window_start")         public String windowStart;
    @JsonProperty("window_end")           public String windowEnd;
    @JsonProperty("timestamp")            public String timestamp;

    public PriceAlert() {}

    /** Legacy constructor used by the fixed-threshold AnomalyDetector; removed in Task 7. */
    public PriceAlert(String symbol, String alertType, BigDecimal priceChangePercent,
                      BigDecimal openPrice, BigDecimal closePrice, Instant windowStart, Instant windowEnd) {
        this.symbol = symbol;
        this.alertType = alertType;
        this.severity = "LOW";
        this.priceChangePercent = priceChangePercent;
        this.oldPrice = openPrice;
        this.newPrice = closePrice;
        this.windowStart = windowStart.toString();
        this.windowEnd = windowEnd.toString();
        this.timestamp = Instant.now().toString();
    }

    /** Build an alert for a candle whose return scored z against the history. */
    public static PriceAlert fromZScore(Candle candle, BigDecimal prevClose, double z) {
        PriceAlert a = new PriceAlert();
        a.symbol = candle.symbol;
        a.alertType = z > 0 ? "PRICE_SPIKE" : "PRICE_DROP";
        a.severity = severityFor(Math.abs(z));
        a.zScore = z;
        a.oldPrice = prevClose;
        a.newPrice = candle.close;
        a.priceChangePercent = candle.close.subtract(prevClose)
                .divide(prevClose, 8, RoundingMode.HALF_EVEN)
                .multiply(HUNDRED)
                .setScale(4, RoundingMode.HALF_EVEN);
        a.windowStart = candle.windowStart.toString();
        a.windowEnd = candle.windowEnd.toString();
        a.timestamp = Instant.now().toString();
        return a;
    }

    public static String severityFor(double absZ) {
        if (absZ >= 8) {
            return "HIGH";
        }
        return absZ >= 6 ? "MEDIUM" : "LOW";
    }

    @Override
    public String toString() {
        return String.format("ALERT [%s] %s %s z=%.2f change=%s%% %s -> %s @ %s",
                severity, symbol, alertType, zScore, priceChangePercent, oldPrice, newPrice, windowStart);
    }
}
```

- [ ] **Step 5: Fix the two getter calls in `CryptoPriceAggregator.PriceAlertSerializer`**

In `CryptoPriceAggregator.java`, change `alert.getSymbol()` to `alert.symbol` and `alert.getAlertType()` to `alert.alertType`, in every occurrence inside `PriceAlertSerializer` (5 in total, spread across 3 lines). Verify with `grep -n 'getSymbol()\|getAlertType()' src/flink_jobs/src/main/java/com/crypto/analyzer/CryptoPriceAggregator.java`, which should print nothing.

- [ ] **Step 6: Create `functions/ZScoreAnomalyDetector.java`**

```java
package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.DetectorState;
import com.crypto.analyzer.models.PriceAlert;
import org.apache.flink.api.common.state.StateTtlConfig;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.api.common.time.Time;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.functions.KeyedProcessFunction;
import org.apache.flink.util.Collector;

/**
 * Flags a 1-minute candle whose log return is more than 4 standard deviations from the
 * symbol's exponentially weighted history (~60-candle span).
 *
 * <p>Rules: no alerts until 30 returns are seen, candles with fewer than 5 trades are not
 * scored, and only adjacent minutes are compared (after a quiet minute the detector
 * re-anchors instead of scoring a multi-minute move). The return is folded into the
 * history after scoring, so an outlier cannot mask itself. Thresholds stay constants
 * until sub-project 4 evaluates them.
 */
public class ZScoreAnomalyDetector extends KeyedProcessFunction<String, Candle, PriceAlert> {

    private static final long serialVersionUID = 1L;

    static final int WARMUP_RETURNS = 30;
    static final int MIN_TRADES = 5;
    static final double Z_THRESHOLD = 4.0;
    /** price_alerts.z_score is DECIMAL(10,4); an unclamped z from a near-flat history would overflow it. */
    static final double Z_CLAMP = 9999.0;
    private static final long ONE_MINUTE_MS = 60_000L;

    private transient ValueState<DetectorState> state;

    @Override
    public void open(Configuration parameters) {
        StateTtlConfig ttl = StateTtlConfig.newBuilder(Time.hours(1))
                .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
                .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
                .build();
        ValueStateDescriptor<DetectorState> descriptor =
                new ValueStateDescriptor<>("zscore-state", DetectorState.class);
        descriptor.enableTimeToLive(ttl);
        state = getRuntimeContext().getState(descriptor);
    }

    @Override
    public void processElement(Candle c, Context ctx, Collector<PriceAlert> out) throws Exception {
        DetectorState s = state.value();
        long start = c.windowStart.toEpochMilli();

        if (s == null) {
            s = new DetectorState();
        } else if (start - s.prevWindowStartMs == ONE_MINUTE_MS) {
            double r = Math.log(c.close.doubleValue() / s.prevClose.doubleValue());
            double z = s.zScore(r);
            if (s.returnsSeen >= WARMUP_RETURNS && c.tradeCount >= MIN_TRADES && Math.abs(z) > Z_THRESHOLD) {
                out.collect(PriceAlert.fromZScore(c, s.prevClose, Math.max(-Z_CLAMP, Math.min(Z_CLAMP, z))));
            }
            s.update(r);
        }
        // Non-adjacent candles (a quiet gap or a replayed window) only move the anchor.
        s.prevClose = c.close;
        s.prevWindowStartMs = start;
        state.update(s);
    }
}
```

- [ ] **Step 7: Run all the Java tests to verify they pass and the job still compiles**

Run: `mvn -q -f src/flink_jobs/pom.xml test`
Expected: exit code 0 (the CandleAggregator, DedupByTradeId and ZScoreAnomalyDetector suites all pass).

- [ ] **Step 8: Commit**

```bash
git add src/flink_jobs/src
git commit -m "feat(flink): EWMA z-score anomaly detector with severity bands and clamped z

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Wire the Flink job, fix exactly-once and cluster config, delete the old classes

**Files:**
- Create: `.../functions/CandleWindowFunction.java`, `.../functions/LateTradeCounter.java`, `.../sinks/JdbcSinks.java`
- Rewrite: `.../CryptoPriceAggregator.java`
- Modify: `.../sinks/RedisSinkFunction.java`, `.../models/PriceAlert.java` (remove the legacy constructor), `configs/flink-conf.yaml`, `docker-compose.yml`
- Delete: `.../models/PriceUpdate.java`, `.../models/OHLCCandle.java`, `.../models/OhlcDatabaseRecord.java`, `.../functions/OHLCAggregator.java`, `.../functions/OHLCWindowFunction.java`, `.../functions/AnomalyDetector.java`, `.../utils/CryptoIdMapper.java`

**Interfaces:**
- Consumes: `Trade`, `Candle`, `CandleAggregator` (Task 4); `DedupByTradeId` (Task 5); `ZScoreAnomalyDetector`, `PriceAlert` (Task 6); the schema from Task 1.
- Produces: rows in `raw_trades`, `price_aggregates_1m` and `price_alerts`; Redis key `crypto:{SYMBOL}:latest` plus Pub/Sub channel `crypto:updates` (Candle JSON); Kafka `crypto-alerts` (PriceAlert JSON, transactional).

- [ ] **Step 1: Create `functions/CandleWindowFunction.java`**

```java
package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Candle;
import org.apache.flink.streaming.api.functions.windowing.ProcessWindowFunction;
import org.apache.flink.streaming.api.windowing.windows.TimeWindow;
import org.apache.flink.util.Collector;

import java.time.Instant;

/** Stamps the aggregated candle with its window bounds. */
public class CandleWindowFunction extends ProcessWindowFunction<Candle, Candle, String, TimeWindow> {

    private static final long serialVersionUID = 1L;

    @Override
    public void process(String key, Context ctx, Iterable<Candle> elements, Collector<Candle> out) {
        Candle c = elements.iterator().next();
        c.windowStart = Instant.ofEpochMilli(ctx.window().getStart());
        c.windowEnd = Instant.ofEpochMilli(ctx.window().getEnd());
        out.collect(c);
    }
}
```

- [ ] **Step 2: Create `functions/LateTradeCounter.java`**

```java
package com.crypto.analyzer.functions;

import com.crypto.analyzer.models.Trade;
import org.apache.flink.api.common.functions.RichMapFunction;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.metrics.Counter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Counts trades that arrived after their 1-minute window closed (Flink metric: lateTrades). */
public class LateTradeCounter extends RichMapFunction<Trade, Trade> {

    private static final long serialVersionUID = 1L;
    private static final Logger LOG = LoggerFactory.getLogger(LateTradeCounter.class);

    private transient Counter lateTrades;

    @Override
    public void open(Configuration parameters) {
        lateTrades = getRuntimeContext().getMetricGroup().counter("lateTrades");
    }

    @Override
    public Trade map(Trade t) {
        lateTrades.inc();
        LOG.debug("Late trade {} {} at {}", t.symbol, t.tradeId, t.eventTime);
        return t;
    }
}
```

- [ ] **Step 3: Create `sinks/JdbcSinks.java`**

```java
package com.crypto.analyzer.sinks;

import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.PriceAlert;
import com.crypto.analyzer.models.Trade;
import org.apache.flink.connector.jdbc.JdbcConnectionOptions;
import org.apache.flink.connector.jdbc.JdbcExecutionOptions;
import org.apache.flink.connector.jdbc.JdbcSink;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;

/**
 * TimescaleDB sinks.
 *
 * <p>All three are at-least-once: batches flush on checkpoint and can be re-sent after a
 * restart. Idempotent SQL makes the stored result effectively-once: ON CONFLICT DO NOTHING
 * for trades and alerts, an upsert for candles. crypto_id is resolved from the symbol inside
 * the SQL, so there is no Java-side symbol map to keep in sync; unknown symbols insert nothing.
 */
public final class JdbcSinks {

    private JdbcSinks() {}

    private static final String RAW_TRADES_SQL =
            "INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time) "
            + "SELECT id, ?, ?, ?, ?, ?, ?, ? FROM cryptocurrencies WHERE symbol = ? "
            + "ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING";

    private static final String CANDLES_SQL =
            "INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, "
            + "  low_price, close_price, vwap, volume, quote_volume, trade_count) "
            + "SELECT id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ? FROM cryptocurrencies WHERE symbol = ? "
            + "ON CONFLICT (crypto_id, window_start) DO UPDATE SET "
            + "  window_end = EXCLUDED.window_end, open_price = EXCLUDED.open_price, "
            + "  high_price = EXCLUDED.high_price, low_price = EXCLUDED.low_price, "
            + "  close_price = EXCLUDED.close_price, vwap = EXCLUDED.vwap, volume = EXCLUDED.volume, "
            + "  quote_volume = EXCLUDED.quote_volume, trade_count = EXCLUDED.trade_count, updated_at = now()";

    private static final String ALERTS_SQL =
            "INSERT INTO price_alerts (crypto_id, alert_type, severity, z_score, price_change_pct, "
            + "  old_price, new_price, window_start, window_end) "
            + "SELECT id, ?, ?, ?, ?, ?, ?, ?, ? FROM cryptocurrencies WHERE symbol = ? "
            + "ON CONFLICT (crypto_id, window_start, alert_type) DO NOTHING";

    public static SinkFunction<Trade> rawTrades(JdbcConnectionOptions conn) {
        return JdbcSink.sink(RAW_TRADES_SQL, (ps, t) -> {
            ps.setLong(1, t.tradeId);
            ps.setBigDecimal(2, t.price);
            ps.setBigDecimal(3, t.size);
            ps.setString(4, t.side);
            ps.setLong(5, t.sequence);
            ps.setObject(6, utc(t.eventTime));
            ps.setObject(7, utc(t.ingestTime));
            ps.setString(8, t.symbol);
        }, batching(500, 1000), conn);
    }

    public static SinkFunction<Candle> candles(JdbcConnectionOptions conn) {
        return JdbcSink.sink(CANDLES_SQL, (ps, c) -> {
            ps.setObject(1, utc(c.windowStart));
            ps.setObject(2, utc(c.windowEnd));
            ps.setBigDecimal(3, c.open);
            ps.setBigDecimal(4, c.high);
            ps.setBigDecimal(5, c.low);
            ps.setBigDecimal(6, c.close);
            ps.setBigDecimal(7, c.vwap);
            ps.setBigDecimal(8, c.volume);
            ps.setBigDecimal(9, c.quoteVolume);
            ps.setInt(10, c.tradeCount);
            ps.setString(11, c.symbol);
        }, batching(100, 1000), conn);
    }

    public static SinkFunction<PriceAlert> alerts(JdbcConnectionOptions conn) {
        return JdbcSink.sink(ALERTS_SQL, (ps, a) -> {
            ps.setString(1, a.alertType);
            ps.setString(2, a.severity);
            ps.setBigDecimal(3, BigDecimal.valueOf(a.zScore).setScale(4, RoundingMode.HALF_EVEN));
            ps.setBigDecimal(4, a.priceChangePercent);
            ps.setBigDecimal(5, a.oldPrice);
            ps.setBigDecimal(6, a.newPrice);
            ps.setObject(7, utc(Instant.parse(a.windowStart)));
            ps.setObject(8, utc(Instant.parse(a.windowEnd)));
            ps.setString(9, a.symbol);
        }, batching(1, 1000), conn);
    }

    private static OffsetDateTime utc(Instant instant) {
        return OffsetDateTime.ofInstant(instant, ZoneOffset.UTC);
    }

    private static JdbcExecutionOptions batching(int size, long intervalMs) {
        return JdbcExecutionOptions.builder()
                .withBatchSize(size)
                .withBatchIntervalMs(intervalMs)
                .withMaxRetries(3)
                .build();
    }
}
```

- [ ] **Step 4: Retype `sinks/RedisSinkFunction.java` to `Candle`**

Change the import `com.crypto.analyzer.models.OHLCCandle` to `com.crypto.analyzer.models.Candle`, the class declaration to `public class RedisSinkFunction extends RichSinkFunction<Candle> {`, and the method signature to `public void invoke(Candle candle, Context context) throws Exception {`. The body keeps compiling as-is, because `Candle` has `getSymbol()`. Also replace the class Javadoc's first sentence with: `Writes the latest 1-minute Candle per symbol to Redis (write-through, 300 s TTL) and publishes it on Pub/Sub. At-least-once: a replay after restart overwrites the same key and may re-publish, which clients tolerate by keying on windowStart.`

- [ ] **Step 5: Rewrite `CryptoPriceAggregator.java`**

```java
package com.crypto.analyzer;

import com.crypto.analyzer.functions.CandleAggregator;
import com.crypto.analyzer.functions.CandleWindowFunction;
import com.crypto.analyzer.functions.DedupByTradeId;
import com.crypto.analyzer.functions.LateTradeCounter;
import com.crypto.analyzer.functions.ZScoreAnomalyDetector;
import com.crypto.analyzer.models.Candle;
import com.crypto.analyzer.models.PriceAlert;
import com.crypto.analyzer.models.Trade;
import com.crypto.analyzer.sinks.JdbcSinks;
import com.crypto.analyzer.sinks.RedisSinkFunction;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.serialization.AbstractDeserializationSchema;
import org.apache.flink.api.common.serialization.SerializationSchema;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.connector.jdbc.JdbcConnectionOptions;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.SingleOutputStreamOperator;
import org.apache.flink.streaming.api.environment.CheckpointConfig;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.sink.DiscardingSink;
import org.apache.flink.streaming.api.windowing.assigners.TumblingEventTimeWindows;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.util.OutputTag;
import org.apache.kafka.clients.consumer.OffsetResetStrategy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * Coinbase trades → dedup → raw trades + 1-minute OHLCV (+ Redis) → z-score alerts.
 *
 * <p>Delivery guarantees: the Kafka alert sink is exactly-once (transactions committed on
 * checkpoint). The JDBC sinks are at-least-once with idempotent SQL, so the result is
 * effectively-once. Redis is at-least-once with idempotent overwrites.
 */
public class CryptoPriceAggregator {

    private static final Logger LOG = LoggerFactory.getLogger(CryptoPriceAggregator.class);

    private static final String KAFKA_BOOTSTRAP_SERVERS = getEnvOrDefault("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092");
    private static final String INPUT_TOPIC = getEnvOrDefault("KAFKA_INPUT_TOPIC", "crypto-trades");
    private static final String ALERT_TOPIC = getEnvOrDefault("KAFKA_ALERT_TOPIC", "crypto-alerts");
    private static final String CONSUMER_GROUP_ID = getEnvOrDefault("KAFKA_CONSUMER_GROUP", "flink-crypto-trades");

    private static final String POSTGRES_URL = String.format("jdbc:postgresql://%s:%s/%s",
            getEnvOrDefault("POSTGRES_HOST", "postgres"),
            getEnvOrDefault("POSTGRES_PORT", "5432"),
            getEnvOrDefault("POSTGRES_DB", "crypto_db"));
    private static final String POSTGRES_USER = getEnvOrDefault("POSTGRES_USER", "crypto_user");
    private static final String POSTGRES_PASSWORD = getEnvOrDefault("POSTGRES_PASSWORD", "crypto_pass");

    private static final String REDIS_HOST = getEnvOrDefault("REDIS_HOST", "redis");
    private static final int REDIS_PORT = Integer.parseInt(getEnvOrDefault("REDIS_PORT", "6379"));

    // One subtask per crypto-trades partition (the topic is created with 4).
    private static final int PARALLELISM = Integer.parseInt(getEnvOrDefault("FLINK_PARALLELISM", "4"));

    private static final OutputTag<Trade> LATE_TRADES = new OutputTag<Trade>("late-trades") {};

    private static String getEnvOrDefault(String key, String defaultValue) {
        String value = System.getenv(key);
        if (value == null || value.trim().isEmpty()) {
            LOG.info("Using default for {}: {}", key, key.contains("PASSWORD") ? "****" : defaultValue);
            return defaultValue;
        }
        LOG.info("Using env for {}: {}", key, key.contains("PASSWORD") ? "****" : value);
        return value;
    }

    public static void main(String[] args) throws Exception {
        final StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(PARALLELISM);

        // Checkpointing is defined here only, not in flink-conf.yaml. Kafka alert transactions
        // commit on each checkpoint, so 30 s is also the worst-case delay before a
        // read_committed consumer sees an alert. Storage comes from state.checkpoints.dir
        // (the shared flink_data volume, set in docker-compose.yml).
        env.enableCheckpointing(30_000, CheckpointingMode.EXACTLY_ONCE);
        CheckpointConfig cp = env.getCheckpointConfig();
        cp.setCheckpointTimeout(120_000);
        cp.setMinPauseBetweenCheckpoints(10_000);
        cp.setMaxConcurrentCheckpoints(1);
        cp.setExternalizedCheckpointCleanup(CheckpointConfig.ExternalizedCheckpointCleanup.RETAIN_ON_CANCELLATION);

        KafkaSource<Trade> source = KafkaSource.<Trade>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setTopics(INPUT_TOPIC)
                .setGroupId(CONSUMER_GROUP_ID)
                // Resume from committed offsets when there is no checkpoint; earliest on first start.
                .setStartingOffsets(OffsetsInitializer.committedOffsets(OffsetResetStrategy.EARLIEST))
                .setValueOnlyDeserializer(new TradeDeserializer())
                .build();

        WatermarkStrategy<Trade> watermarks = WatermarkStrategy
                .<Trade>forBoundedOutOfOrderness(Duration.ofSeconds(2))
                .withTimestampAssigner((trade, recordTs) -> trade.getEventTimeMillis())
                // A partition with no trades for 30 s (quiet coins at night) must not stall windows.
                .withIdleness(Duration.ofSeconds(30));

        DataStream<Trade> trades = env
                .fromSource(source, watermarks, "Coinbase Trades")
                .keyBy(Trade::getSymbol)
                .process(new DedupByTradeId())
                .name("Dedup by trade_id");

        JdbcConnectionOptions pg = new JdbcConnectionOptions.JdbcConnectionOptionsBuilder()
                .withUrl(POSTGRES_URL)
                .withDriverName("org.postgresql.Driver")
                .withUsername(POSTGRES_USER)
                .withPassword(POSTGRES_PASSWORD)
                .build();

        trades.addSink(JdbcSinks.rawTrades(pg)).name("raw_trades Sink");

        SingleOutputStreamOperator<Candle> candles = trades
                .keyBy(Trade::getSymbol)
                .window(TumblingEventTimeWindows.of(Time.minutes(1)))
                .sideOutputLateData(LATE_TRADES)
                .aggregate(new CandleAggregator(), new CandleWindowFunction())
                .name("1-Min OHLCV");

        candles.getSideOutput(LATE_TRADES)
                .map(new LateTradeCounter()).name("Count Late Trades")
                .addSink(new DiscardingSink<>()).name("Discard Late Trades");

        candles.addSink(JdbcSinks.candles(pg)).name("price_aggregates_1m Sink");
        candles.addSink(new RedisSinkFunction(REDIS_HOST, REDIS_PORT, 300)).name("Redis Latest + Pub/Sub");

        DataStream<PriceAlert> alerts = candles
                .keyBy(Candle::getSymbol)
                .process(new ZScoreAnomalyDetector())
                .name("Z-Score Anomaly Detector");

        alerts.addSink(JdbcSinks.alerts(pg)).name("price_alerts Sink");

        KafkaSink<PriceAlert> alertSink = KafkaSink.<PriceAlert>builder()
                .setBootstrapServers(KAFKA_BOOTSTRAP_SERVERS)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(ALERT_TOPIC)
                        .setValueSerializationSchema(new PriceAlertSerializer())
                        .build())
                .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
                // Required for EXACTLY_ONCE: unique transactional ids across restarts.
                .setTransactionalIdPrefix("crypto-alerts")
                // Flink's default producer transaction timeout (1 h) exceeds the broker's
                // transaction.max.timeout.ms (15 min) and fails the job; stay at the broker cap.
                .setProperty("transaction.timeout.ms", "900000")
                .build();

        alerts.sinkTo(alertSink).name("crypto-alerts Kafka Sink (exactly-once)");

        env.execute("Crypto trades -> OHLCV + z-score alerts");
    }

    /** Kafka JSON to Trade. Malformed or invalid records return null, which the Kafka source skips. */
    private static class TradeDeserializer extends AbstractDeserializationSchema<Trade> {

        private static final long serialVersionUID = 1L;
        private transient ObjectMapper mapper;

        @Override
        public void open(InitializationContext context) {
            mapper = new ObjectMapper().registerModule(new JavaTimeModule());
        }

        @Override
        public Trade deserialize(byte[] message) {
            try {
                Trade t = mapper.readValue(message, Trade.class);
                if (t.isValid()) {
                    return t;
                }
                LOG.warn("Dropping invalid trade: {}", new String(message, StandardCharsets.UTF_8));
            } catch (IOException e) {
                LOG.warn("Dropping undeserializable record: {}", e.getMessage());
            }
            return null;
        }
    }

    private static class PriceAlertSerializer implements SerializationSchema<PriceAlert> {

        private static final long serialVersionUID = 1L;
        private static final ObjectMapper MAPPER = new ObjectMapper();

        @Override
        public byte[] serialize(PriceAlert alert) {
            try {
                return MAPPER.writeValueAsBytes(alert);
            } catch (IOException e) {
                // Fail the job rather than write a placeholder into an exactly-once topic.
                throw new IllegalStateException("Cannot serialize alert for " + alert.symbol, e);
            }
        }
    }
}
```

- [ ] **Step 6: Delete the old classes and the legacy constructor**

```bash
cd src/flink_jobs/src/main/java/com/crypto/analyzer
git rm -q models/PriceUpdate.java models/OHLCCandle.java models/OhlcDatabaseRecord.java \
    functions/OHLCAggregator.java functions/OHLCWindowFunction.java functions/AnomalyDetector.java \
    utils/CryptoIdMapper.java
cd -
```

In `models/PriceAlert.java`, delete the constructor documented as `Legacy constructor used by the fixed-threshold AnomalyDetector; removed in Task 7.`, including its Javadoc.

- [ ] **Step 7: Fix the Flink cluster config**

In `configs/flink-conf.yaml`:
- Delete the first `taskmanager.numberOfTaskSlots: 2` line (the one under "TaskManager Configuration") and the first `parallelism.default: 2` line (under "Parallelism Configuration"). The later `4` values remain.
- Delete the five `execution.checkpointing.*` lines under "Checkpointing Configuration" and replace them with the comment `# Checkpointing (interval, mode, timeout) is set in CryptoPriceAggregator.java only.`

In `docker-compose.yml`, in the **jobmanager** `FLINK_PROPERTIES` block, append these lines (same indentation as `parallelism.default: 4`):

```yaml
        # Job-level settings belong on the JobManager, which does not mount configs/flink-conf.yaml.
        state.backend.type: rocksdb
        state.backend.incremental: true
        state.checkpoints.dir: file:///opt/flink/data/checkpoints
        state.savepoints.dir: file:///opt/flink/data/savepoints
        restart-strategy.type: exponential-delay
        restart-strategy.exponential-delay.initial-backoff: 10s
        restart-strategy.exponential-delay.max-backoff: 2min
        restart-strategy.exponential-delay.backoff-multiplier: 2.0
```

In both `FLINK_PROPERTIES` comments (jobmanager and taskmanager), replace `matches crypto-prices Kafka partitions` with `matches crypto-trades Kafka partitions`.

- [ ] **Step 8: Build and verify**

```bash
mvn -q -f src/flink_jobs/pom.xml clean package
grep -rnwE 'OHLCCandle|PriceUpdate|OhlcDatabaseRecord|CryptoIdMapper|OHLCAggregator|AnomalyDetector|setCheckpointStorage' src/flink_jobs/src || echo "no stale references"
unzip -l src/flink_jobs/target/crypto-analyzer-flink-1.0.0.jar | grep -E 'JdbcSinks|ZScoreAnomalyDetector|DedupByTradeId'
docker compose config -q && echo "compose ok"
```

Expected: the build succeeds with all tests passing, the output shows `no stale references`, the three classes are listed in the JAR, and `compose ok` is printed. `-w` matches whole words, so `ZScoreAnomalyDetector` does not count as a hit for `AnomalyDetector`.

- [ ] **Step 9: Commit**

```bash
git add -A src/flink_jobs configs/flink-conf.yaml docker-compose.yml
git commit -m "feat(flink): trade pipeline with idempotent JDBC sinks and working exactly-once alerts

- Kafka alert sink gets transactionalIdPrefix and a 15 min transaction timeout
- JobManager now carries RocksDB, restart strategy and shared checkpoint dir
- 5/15-min Flink windows removed (TimescaleDB continuous aggregates)
- late trades counted via side output

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: API symbol registry

**Files:**
- Create: `src/api/registry.py`, `tests/api/conftest.py`, `tests/api/test_symbols_api.py`
- Modify: `src/api/database.py`, `src/api/config.py`, `src/api/endpoints/symbols.py` (`list_symbols` only), `src/api/endpoints/historical.py` (`_validate_symbol` and its callers), `src/api/endpoints/alerts.py` (symbol check), `src/api/endpoints/websocket.py`

**Interfaces:**
- Consumes: `src.symbols.fetch_symbols`, `Symbol` (Task 2).
- Produces:
  - `src.api.registry.symbols_of(conn_owner) -> dict[str, Symbol]`, which reads `conn_owner.app.state.symbols` (works for `Request` and `WebSocket`).
  - `src.api.registry.require_symbol(symbols: dict[str, Symbol], raw: str, allow_all: bool = False) -> str`, which returns the upper-cased symbol or raises `HTTPException(400)`.
  - `src.api.database.get_pool(request) -> asyncpg.Pool`.
  - The test fixture `fakes`, returning `(client, conn, redis)`, where `conn` is a `FakeConn` with `fetch_result`, `fetchrow_result`, `fetchval_result` and `queries`, and `redis` is a `FakeRedis` with a `store` dict. Tasks 9 and 10 reuse it.

- [ ] **Step 1: Write the fixture and the failing tests**

`tests/api/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient

from src.api.database import get_db, get_pool, get_redis
from src.api.main import app
from src.symbols import Symbol

SYMBOLS = {
    "BTC": Symbol("BTC", "Bitcoin", "bitcoin", "BTC-USD"),
    "POL": Symbol("POL", "Polygon", "polygon-ecosystem-token", "POL-USD"),
}


class FakeConn:
    """Stands in for an asyncpg connection or pool: returns canned rows and records every query."""

    def __init__(self):
        self.fetch_result = []
        self.fetchrow_result = None
        self.fetchval_result = 0
        self.queries = []

    async def fetch(self, sql, *args):
        self.queries.append((sql, args))
        return self.fetch_result

    async def fetchrow(self, sql, *args):
        self.queries.append((sql, args))
        return self.fetchrow_result

    async def fetchval(self, sql, *args):
        self.queries.append((sql, args))
        return self.fetchval_result


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)


@pytest.fixture
def fakes():
    conn, redis = FakeConn(), FakeRedis()
    app.state.symbols = SYMBOLS

    async def _db():
        yield conn

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_pool] = lambda: conn
    app.dependency_overrides[get_redis] = lambda: redis
    # No `with` block: the lifespan (real DB/Redis connections) must not run in unit tests.
    yield TestClient(app), conn, redis
    app.dependency_overrides.clear()
```

`tests/api/test_symbols_api.py`:

```python
def test_symbols_come_from_the_registry(fakes):
    client, _, _ = fakes
    body = client.get("/api/v1/symbols").json()
    assert body["count"] == 2
    assert {"symbol": "POL", "name": "Polygon", "slug": "polygon-ecosystem-token"} in body["symbols"]


def test_unknown_symbol_is_rejected_with_supported_list(fakes):
    client, _, _ = fakes
    r = client.get("/api/v1/historical/MATIC")
    assert r.status_code == 400
    assert "Supported: BTC, POL" in r.json()["detail"]


def test_alerts_accept_all(fakes):
    client, _, _ = fakes
    assert client.get("/api/v1/alerts/ALL").status_code == 200
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/python -m pytest tests/api/test_symbols_api.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_pool' from 'src.api.database'`.

- [ ] **Step 3: Create `src/api/registry.py`**

```python
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
```

- [ ] **Step 4: Load the registry in `src/api/database.py` and add `get_pool`**

Add the import `from ..symbols import fetch_symbols` next to `from .config import settings`. In `lifespan`, directly after the `app.state.db_pool = await asyncpg.create_pool(...)` statement, add:

```python
    app.state.symbols = await fetch_symbols(app.state.db_pool)
```

and include the symbols in the "Connected to..." log line by appending `" (%d symbols)"` to the format and `len(app.state.symbols)` to the arguments. At the end of the file, add:

```python
async def get_pool(request: Request) -> asyncpg.Pool:
    """The shared pool, for handlers that only sometimes need the database (e.g. cache fallback)."""
    return request.app.state.db_pool
```

- [ ] **Step 5: Remove the hard-coded lists from `src/api/config.py`**

Delete the `SUPPORTED_SYMBOLS` and `SYMBOL_METADATA` settings, together with their comment line. Change `CORS_ORIGINS` to `["http://localhost:3000"]`.

- [ ] **Step 6: Switch the endpoints to the registry**

`src/api/endpoints/symbols.py`: add `Request` to the fastapi import and `from ..registry import symbols_of`. Replace `list_symbols` with:

```python
async def list_symbols(request: Request):
    symbols = symbols_of(request)
    return {
        "symbols": [
            {"symbol": s.symbol, "name": s.name, "slug": s.coingecko_id}
            for s in symbols.values()
        ],
        "count": len(symbols),
    }
```

(`trending_symbols` is rewritten in Task 10; for now change only its `list(settings.SUPPORTED_SYMBOLS)` argument to `list(symbols_of(request))` and add `request: Request` as its first parameter.)

`src/api/endpoints/historical.py`: add `Request` to the fastapi import and `from ..registry import require_symbol, symbols_of`, then delete `_validate_symbol`. In each of the three handlers, add `request: Request` as the first parameter and replace `symbol = _validate_symbol(symbol)` with `symbol = require_symbol(symbols_of(request), symbol)`.

`src/api/endpoints/alerts.py`: add `Request` to the fastapi import and `from ..registry import require_symbol, symbols_of`. Add `request: Request` as the first parameter of `get_alerts` and `get_all_alerts`. In `get_alerts`, replace `symbol = symbol.upper()` with `symbol = require_symbol(symbols_of(request), symbol, allow_all=True)` and delete the inner `if symbol not in settings.SUPPORTED_SYMBOLS: raise ...` block. Change `get_all_alerts`'s body to `return await get_alerts(request, response, "ALL", limit, hours, conn)`. (Task 10 rewrites the SQL.)

`src/api/endpoints/websocket.py`:
- Add `from ..registry import symbols_of` and remove `from ..config import settings`.
- In `ConnectionManager.__init__`, set `self.connections: dict[str, Set[WebSocket]] = {"ALL": set()}`. `connect()` already adds per-symbol sets lazily.
- In `websocket_prices`, replace `if symbol != "ALL" and symbol not in settings.SUPPORTED_SYMBOLS:` with `if symbol != "ALL" and symbol not in symbols_of(websocket):`.
- Replace `symbols = list(settings.SUPPORTED_SYMBOLS) if symbol == "ALL" else [symbol]` with `symbols = list(symbols_of(websocket)) if symbol == "ALL" else [symbol]`.

- [ ] **Step 7: Run the tests to verify they pass, and check for stragglers**

```bash
venv/bin/python -m pytest tests/api/test_symbols_api.py -v
grep -rn 'SUPPORTED_SYMBOLS\|SYMBOL_METADATA' src || echo "no hard-coded symbol lists"
```

Expected: `3 passed`, followed by `no hard-coded symbol lists`.

- [ ] **Step 8: Commit**

```bash
git add -A src/api tests/api
git commit -m "feat(api): serve and validate symbols from the cryptocurrencies table

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `/latest` with a Redis→TimescaleDB fallback

**Files:**
- Rewrite: `src/api/endpoints/latest.py`
- Modify: `src/api/models.py` (`LatestPriceResponse`, `HistoricalPriceResponse`)
- Test: `tests/api/test_latest.py`

**Interfaces:**
- Consumes: the `fakes` fixture, `get_pool`, `require_symbol`, `symbols_of` (Task 8); the Redis Candle JSON (Task 4); `price_aggregates_1m` (Task 1).
- Produces:
  - `LatestPriceResponse(symbol, window_start, window_end, open, high, low, close, vwap, volume, quote_volume, trade_count)`.
  - `HistoricalPriceResponse(symbol, window_start, window_end, open_price, high_price, low_price, close_price, vwap, volume, quote_volume, trade_count)`.
  - Response header `X-Data-Source: redis|postgres` on `/latest/{symbol}`.

- [ ] **Step 1: Write the failing tests**

`tests/api/test_latest.py`:

```python
import json
from datetime import datetime, timezone
from decimal import Decimal

from redis.exceptions import ConnectionError as RedisConnectionError

CANDLE_JSON = json.dumps({
    "symbol": "BTC", "windowStart": 1767225600.0, "windowEnd": 1767225660.0,
    "open": 100, "high": 110, "low": 90, "close": 105, "vwap": 101.5,
    "volume": 2.5, "quoteVolume": 253.75, "tradeCount": 7,
})


def db_row(symbol="BTC"):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "symbol": symbol, "window_start": start, "window_end": start.replace(minute=1),
        "open_price": Decimal("100"), "high_price": Decimal("110"), "low_price": Decimal("90"),
        "close_price": Decimal("105"), "vwap": Decimal("101.5"), "volume": Decimal("2.5"),
        "quote_volume": Decimal("253.75"), "trade_count": 7,
    }


def test_cache_hit_is_served_from_redis(fakes):
    client, conn, redis = fakes
    redis.store["crypto:BTC:latest"] = CANDLE_JSON
    r = client.get("/api/v1/latest/BTC")
    assert r.status_code == 200
    assert r.headers["X-Data-Source"] == "redis"
    body = r.json()
    assert body["trade_count"] == 7
    assert body["window_start"].startswith("2026-01-01T00:00:00")
    assert conn.queries == []


def test_cache_miss_falls_back_to_postgres(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [db_row()]
    r = client.get("/api/v1/latest/BTC")
    assert r.status_code == 200
    assert r.headers["X-Data-Source"] == "postgres"
    assert Decimal(r.json()["vwap"]) == Decimal("101.5")
    assert conn.queries[0][1] == (["BTC"],)


def test_redis_outage_still_serves_postgres(fakes):
    client, conn, redis = fakes

    async def broken_get(key):
        raise RedisConnectionError("redis down")

    redis.get = broken_get
    conn.fetch_result = [db_row()]
    r = client.get("/api/v1/latest/BTC")
    assert r.status_code == 200
    assert r.headers["X-Data-Source"] == "postgres"


def test_corrupt_cache_entry_falls_back_to_postgres(fakes):
    client, conn, redis = fakes
    redis.store["crypto:BTC:latest"] = "{not json"
    conn.fetch_result = [db_row()]
    assert client.get("/api/v1/latest/BTC").headers["X-Data-Source"] == "postgres"


def test_no_data_anywhere_is_404(fakes):
    client, _, _ = fakes
    assert client.get("/api/v1/latest/BTC").status_code == 404


def test_all_mixes_sources_and_only_queries_misses(fakes):
    client, conn, redis = fakes
    redis.store["crypto:BTC:latest"] = CANDLE_JSON
    conn.fetch_result = [db_row("POL")]
    r = client.get("/api/v1/latest/all")
    assert r.status_code == 200
    assert set(r.json()["prices"]) == {"BTC", "POL"}
    assert r.headers["X-Cache-Hits"] == "1"
    assert conn.queries[0][1] == (["POL"],)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/python -m pytest tests/api/test_latest.py -v`
Expected: FAIL. The cache-hit test raises `KeyError: 'volumeSum'`, and the fallback tests get 404 instead of 200.

- [ ] **Step 3: Update `src/api/models.py`**

Replace the `LatestPriceResponse` and `HistoricalPriceResponse` classes with:

```python
class LatestPriceResponse(BaseModel):
    """Most recent completed 1-minute candle. X-Data-Source says whether Redis or PostgreSQL served it."""
    symbol: str
    window_start: datetime
    window_end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    vwap: Decimal = Field(..., description="Volume-weighted average price")
    volume: Decimal = Field(..., description="Base-asset units traded")
    quote_volume: Decimal = Field(..., description="USD traded (sum of price * size)")
    trade_count: int = Field(..., description="Number of trades in the window")


class HistoricalPriceResponse(BaseModel):
    """One persisted 1-minute candle from price_aggregates_1m."""
    symbol: str
    window_start: datetime
    window_end: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    vwap: Decimal
    volume: Decimal
    quote_volume: Decimal
    trade_count: int
```

- [ ] **Step 4: Rewrite `src/api/endpoints/latest.py`**

```python
"""
Latest-candle endpoints.

Redis holds the newest 1-minute candle per symbol (written by Flink on window close).
On a miss, a corrupt entry, or a Redis outage, the newest row in TimescaleDB is served
instead, so Redis is a cache in front of the database rather than the only source.
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from redis.exceptions import RedisError

from ..database import get_pool, get_redis
from ..models import ErrorResponse, LatestPriceResponse
from ..registry import require_symbol, symbols_of

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/latest", tags=["Latest Prices"])

# One index-backed LIMIT 1 per symbol (PK is crypto_id, window_start).
LATEST_SQL = """
    SELECT c.symbol, p.window_start, p.window_end, p.open_price, p.high_price, p.low_price,
           p.close_price, p.vwap, p.volume, p.quote_volume, p.trade_count
    FROM cryptocurrencies c
    CROSS JOIN LATERAL (
        SELECT * FROM price_aggregates_1m
        WHERE crypto_id = c.id
        ORDER BY window_start DESC
        LIMIT 1
    ) p
    WHERE c.symbol = ANY($1::text[])
"""


def _from_cache(raw: str) -> LatestPriceResponse:
    """Parse the Flink Candle JSON (camelCase keys, window times in epoch seconds).
    parse_float=Decimal keeps Java BigDecimal prices exact."""
    d = json.loads(raw, parse_float=Decimal)
    return LatestPriceResponse(
        symbol=d["symbol"],
        window_start=datetime.fromtimestamp(float(d["windowStart"]), tz=timezone.utc),
        window_end=datetime.fromtimestamp(float(d["windowEnd"]), tz=timezone.utc),
        open=d["open"], high=d["high"], low=d["low"], close=d["close"],
        vwap=d["vwap"], volume=d["volume"], quote_volume=d["quoteVolume"], trade_count=d["tradeCount"],
    )


def _from_row(row) -> LatestPriceResponse:
    return LatestPriceResponse(
        symbol=row["symbol"], window_start=row["window_start"], window_end=row["window_end"],
        open=row["open_price"], high=row["high_price"], low=row["low_price"], close=row["close_price"],
        vwap=row["vwap"], volume=row["volume"], quote_volume=row["quote_volume"], trade_count=row["trade_count"],
    )


async def _latest(symbols: list[str], redis_client, pool) -> tuple[dict, dict]:
    """Newest candle per symbol: Redis first, one PostgreSQL query for all misses.
    Returns (candles by symbol, source by symbol)."""
    candles, sources = {}, {}
    for sym in symbols:
        try:
            raw = await redis_client.get(f"crypto:{sym}:latest")
            if raw is not None:
                candles[sym], sources[sym] = _from_cache(raw), "redis"
        except RedisError as e:
            logger.warning("Redis unavailable for %s, falling back to PostgreSQL: %s", sym, e)
        except (ValueError, KeyError) as e:
            logger.warning("Corrupt cache entry for %s, falling back to PostgreSQL: %s", sym, e)

    misses = [s for s in symbols if s not in candles]
    if misses:
        for row in await pool.fetch(LATEST_SQL, misses):
            candles[row["symbol"]], sources[row["symbol"]] = _from_row(row), "postgres"
    return candles, sources


@router.get("/all", summary="Latest candle for every tracked symbol")
async def get_all_latest_prices(
    request: Request,
    response: Response,
    redis_client=Depends(get_redis),
    pool=Depends(get_pool),
):
    symbols = list(symbols_of(request))
    candles, sources = await _latest(symbols, redis_client, pool)
    hits = sum(1 for s in sources.values() if s == "redis")
    hit_rate = f"{hits / len(symbols) * 100:.1f}%"
    response.headers["X-Total-Symbols"] = str(len(symbols))
    response.headers["X-Cache-Hits"] = str(hits)
    response.headers["X-Cache-Hit-Rate"] = hit_rate

    if not candles:
        raise HTTPException(status_code=404, detail="No candles yet for any symbol")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prices": {sym: c.model_dump(mode="json") for sym, c in candles.items()},
        "cache_hit_rate": hit_rate,
    }


@router.get(
    "/{symbol}",
    response_model=LatestPriceResponse,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
    summary="Latest candle for one symbol",
)
async def get_latest_price(
    symbol: str,
    request: Request,
    response: Response,
    redis_client=Depends(get_redis),
    pool=Depends(get_pool),
) -> LatestPriceResponse:
    symbol = require_symbol(symbols_of(request), symbol)
    candles, sources = await _latest([symbol], redis_client, pool)
    if symbol not in candles:
        raise HTTPException(
            status_code=404,
            detail=f"No candle for {symbol} yet; the first one appears after the first full minute of trades.",
        )
    candle = candles[symbol]
    response.headers["X-Data-Source"] = sources[symbol]
    response.headers["X-Cache-Hit"] = str(sources[symbol] == "redis").lower()
    response.headers["X-Data-Age-Seconds"] = str(
        int((datetime.now(timezone.utc) - candle.window_end).total_seconds())
    )
    return candle
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `venv/bin/python -m pytest tests/api/test_latest.py -v`
Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/api/models.py src/api/endpoints/latest.py tests/api/test_latest.py
git commit -m "feat(api): Redis-first latest candles with TimescaleDB fallback on miss or outage

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Historical renames, alerts fields, trending from `candles_1h`

**Files:**
- Modify: `src/api/endpoints/historical.py`, `src/api/endpoints/alerts.py`, `src/api/endpoints/symbols.py` (`trending_symbols`)
- Test: `tests/api/test_historical.py`, `tests/api/test_alerts_trending.py`

**Interfaces:**
- Consumes: `HistoricalPriceResponse` (Task 9), the `fakes` fixture (Task 8), `price_alerts` and `candles_1h` (Task 1).
- Produces:
  - Alert JSON `{symbol, alert_type, severity, z_score, price_change_pct, old_price, new_price, window_start, window_end, created_at}`.
  - Trending JSON `{direction, count, trending: [{symbol, name, price, volume_24h, market_cap: null, price_change_24h, timestamp}]}`, the same shape the frontend already parses.

- [ ] **Step 1: Write the failing tests**

`tests/api/test_historical.py`:

```python
from datetime import datetime, timezone
from decimal import Decimal


def row():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "symbol": "BTC", "window_start": start, "window_end": start.replace(minute=1),
        "open_price": Decimal("100"), "high_price": Decimal("110"), "low_price": Decimal("90"),
        "close_price": Decimal("105"), "vwap": Decimal("101.5"), "volume": Decimal("2.5"),
        "quote_volume": Decimal("253.75"), "trade_count": 7,
    }


def test_historical_returns_renamed_fields(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [row()]
    conn.fetchval_result = 1
    body = client.get("/api/v1/historical/BTC").json()
    assert body[0]["vwap"] == "101.5"
    assert body[0]["quote_volume"] == "253.75"
    assert "avg_price" not in body[0] and "volume_sum" not in body[0]


def test_naive_query_times_are_treated_as_utc(fakes):
    client, conn, _ = fakes
    client.get("/api/v1/historical/BTC?start_time=2026-01-01T00:00:00&end_time=2026-01-01T01:00:00")
    _, args = conn.queries[0]
    assert args[1] == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert args[2] == datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)


def test_stats_average_is_volume_weighted(fakes):
    client, conn, _ = fakes
    conn.fetchrow_result = {"lowest": Decimal("90"), "highest": Decimal("110"), "average": Decimal("101"),
                            "total_volume": Decimal("5000"), "candle_count": 3}
    client.get("/api/v1/historical/BTC/stats")
    sql, _ = conn.queries[0]
    assert "SUM(p.quote_volume) / NULLIF(SUM(p.volume), 0)" in sql
```

`tests/api/test_alerts_trending.py`:

```python
from datetime import datetime, timezone
from decimal import Decimal

NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def test_alerts_include_z_score_and_severity(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [{
        "symbol": "BTC", "alert_type": "PRICE_SPIKE", "severity": "HIGH", "z_score": Decimal("9.5"),
        "price_change_pct": Decimal("5.1"), "old_price": Decimal("100"), "new_price": Decimal("105.1"),
        "window_start": NOW, "window_end": NOW, "created_at": NOW,
    }]
    alert = client.get("/api/v1/alerts/BTC").json()["alerts"][0]
    assert alert["severity"] == "HIGH"
    assert alert["z_score"] == 9.5


def test_all_alerts_pass_null_symbol_filter(fakes):
    client, conn, _ = fakes
    client.get("/api/v1/alerts/ALL")
    _, args = conn.queries[0]
    assert args[0] is None


def test_trending_reads_hourly_rollup_and_keeps_frontend_shape(fakes):
    client, conn, _ = fakes
    conn.fetch_result = [{
        "symbol": "BTC", "name": "Bitcoin", "price": Decimal("105"), "volume_24h": Decimal("1000000"),
        "price_change_24h": Decimal("5.0"), "as_of": NOW,
    }]
    body = client.get("/api/v1/trending?direction=gainers").json()
    sql, _ = conn.queries[0]
    assert "candles_1h" in sql
    assert body["trending"][0] == {
        "symbol": "BTC", "name": "Bitcoin", "price": 105.0, "volume_24h": 1000000.0,
        "market_cap": None, "price_change_24h": 5.0, "timestamp": NOW.isoformat(),
    }


def test_trending_with_under_24h_of_data_is_empty_not_an_error(fakes):
    client, conn, _ = fakes
    r = client.get("/api/v1/trending")
    assert r.status_code == 200
    assert r.json() == {"direction": "abs", "count": 0, "trending": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv/bin/python -m pytest tests/api/test_historical.py tests/api/test_alerts_trending.py -v`
Expected: FAIL. You'll see `KeyError: 'avg_price'` in historical, the naive datetime comparing unequal to the aware one, missing `severity`, and `v_latest_prices` in the SQL.

- [ ] **Step 3: Update `src/api/endpoints/historical.py`**

1. Change the `datetime` import to `from datetime import datetime, timedelta, timezone`, and add this helper below the router:

```python
def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Query params without an offset are treated as UTC; the columns are TIMESTAMPTZ."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
```

2. In `get_historical_prices` and `get_price_stats`, replace the defaulting block with:

```python
    end_time = _as_utc(end_time) or datetime.now(timezone.utc)
    start_time = _as_utc(start_time) or end_time - timedelta(hours=24)
```

3. In both candle SELECT lists (`get_historical_prices` and `get_latest_historical`), replace

```sql
                p.avg_price,
                p.volume_sum,
                p.trade_count
```

with

```sql
                p.vwap,
                p.volume,
                p.quote_volume,
                p.trade_count
```

4. In both `HistoricalPriceResponse(...)` constructions, replace `avg_price=row["avg_price"], volume_sum=row["volume_sum"],` with `vwap=row["vwap"], volume=row["volume"], quote_volume=row["quote_volume"],`.

5. In `get_price_stats`, replace the two aggregate lines

```sql
                AVG(p.avg_price)  AS average,
                SUM(p.volume_sum) AS total_volume,
```

with

```sql
                SUM(p.quote_volume) / NULLIF(SUM(p.volume), 0) AS average,       -- VWAP over the range
                SUM(p.quote_volume)                            AS total_volume,  -- USD
```

- [ ] **Step 4: Update `src/api/endpoints/alerts.py`**

Change the `datetime` import to `from datetime import datetime, timedelta, timezone`. Replace `_serialize_alert` and the whole `try:` block of `get_alerts` with:

```python
ALERTS_SQL = """
    SELECT c.symbol, pa.alert_type, pa.severity, pa.z_score, pa.price_change_pct,
           pa.old_price, pa.new_price, pa.window_start, pa.window_end, pa.created_at
    FROM price_alerts pa
    JOIN cryptocurrencies c ON pa.crypto_id = c.id
    WHERE ($1::text IS NULL OR c.symbol = $1)
      AND pa.created_at >= $2
    ORDER BY pa.created_at DESC
    LIMIT $3
"""


def _serialize_alert(row) -> dict:
    return {
        "symbol": row["symbol"],
        "alert_type": row["alert_type"],
        "severity": row["severity"],
        "z_score": float(row["z_score"]),
        "price_change_pct": float(row["price_change_pct"]),
        "old_price": float(row["old_price"]),
        "new_price": float(row["new_price"]),
        "window_start": row["window_start"].isoformat(),
        "window_end": row["window_end"].isoformat(),
        "created_at": row["created_at"].isoformat(),
    }
```

(Put `ALERTS_SQL` and `_serialize_alert` at module level, above the routes.) The body of `get_alerts` after the `require_symbol` line becomes:

```python
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = await conn.fetch(ALERTS_SQL, None if symbol == "ALL" else symbol, cutoff, limit)
    alerts = [_serialize_alert(row) for row in rows]

    response.headers["X-Total-Alerts"] = str(len(alerts))
    response.headers["X-Lookback-Hours"] = str(hours)
    return {"symbol": symbol, "alert_count": len(alerts), "lookback_hours": hours, "alerts": alerts}
```

Remove the now-unused `from ..config import settings` import. Database errors propagate to the global exception handler in `main.py`.

- [ ] **Step 5: Rewrite `trending_symbols` in `src/api/endpoints/symbols.py`**

Replace the function body (everything after the `order_clause = order_clauses[direction]` line) and update its description:

```python
@router.get(
    "/trending",
    summary="Trending symbols by 24h price change",
    description="24h change from the candles_1h continuous aggregate (hourly granularity; the newest "
                "bucket can lag up to an hour). Empty until 24h of candles exist.",
)
async def trending_symbols(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Max rows to return (1-50)"),
    direction: str = Query("abs", pattern="^(abs|gainers|losers)$",
                           description="Sort: abs (biggest movers), gainers, or losers"),
    conn: asyncpg.Connection = Depends(get_db),
):
    order_clause = {
        "abs": "ABS(price_change_24h) DESC",
        "gainers": "price_change_24h DESC",
        "losers": "price_change_24h ASC",
    }[direction]

    sql = f"""
        WITH latest AS (
            SELECT DISTINCT ON (crypto_id) crypto_id, bucket, close_price
            FROM candles_1h
            WHERE bucket > now() - INTERVAL '2 days'
            ORDER BY crypto_id, bucket DESC
        ),
        day_ago AS (
            SELECT DISTINCT ON (h.crypto_id) h.crypto_id, h.close_price
            FROM candles_1h h
            JOIN latest l ON l.crypto_id = h.crypto_id
            WHERE h.bucket <= l.bucket - INTERVAL '24 hours'
              AND h.bucket >  l.bucket - INTERVAL '48 hours'
            ORDER BY h.crypto_id, h.bucket DESC
        ),
        volume AS (
            SELECT crypto_id, SUM(quote_volume) AS volume_24h
            FROM candles_1h
            WHERE bucket > now() - INTERVAL '24 hours'
            GROUP BY crypto_id
        )
        SELECT * FROM (
            SELECT c.symbol, c.name,
                   l.close_price AS price,
                   v.volume_24h,
                   (l.close_price - d.close_price) / d.close_price * 100 AS price_change_24h,
                   l.bucket + INTERVAL '1 hour' AS as_of
            FROM latest l
            JOIN day_ago d USING (crypto_id)
            JOIN cryptocurrencies c ON c.id = l.crypto_id
            LEFT JOIN volume v USING (crypto_id)
            WHERE c.is_active
        ) t
        ORDER BY {order_clause}
        LIMIT $1
    """
    rows = await conn.fetch(sql, limit)
    return {
        "direction": direction,
        "count": len(rows),
        "trending": [
            {
                "symbol": row["symbol"],
                "name": row["name"],
                "price": float(row["price"]),
                "volume_24h": float(row["volume_24h"]) if row["volume_24h"] is not None else None,
                "market_cap": None,   # not derivable from trades; kept for the frontend schema
                "price_change_24h": float(row["price_change_24h"]),
                "timestamp": row["as_of"].isoformat(),
            }
            for row in rows
        ],
    }
```

Remove the now-unused imports `HTTPException` and `from ..config import settings` from `symbols.py`, but only if nothing else in the file uses them.

- [ ] **Step 6: Run the whole Python suite**

Run: `venv/bin/python -m pytest -v`
Expected: every test passes (Tasks 2, 3 and 8–10).

- [ ] **Step 7: Commit**

```bash
git add src/api tests/api
git commit -m "feat(api): renamed candle fields, alert severity/z-score, trending from candles_1h

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Frontend contract update

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/ws.ts`, `frontend/components/ohlc/CandleTable.tsx`

**Interfaces:**
- Consumes: the API JSON from Tasks 9–10 and the Redis/WS Candle JSON from Task 4.

- [ ] **Step 1: Update the zod schemas in `frontend/lib/types.ts`**

In `candleSchema`, replace

```ts
  volume_sum: z.coerce.number(),
  event_count: z.number(),
```

with

```ts
  vwap: z.coerce.number(),
  volume: z.coerce.number(),
  quote_volume: z.coerce.number(),
  trade_count: z.number(),
```

In `historicalCandleSchema`, replace

```ts
  avg_price: z.coerce.number(),
  volume_sum: z.coerce.number().nullable(),
  trade_count: z.number().nullable(),
```

with

```ts
  vwap: z.coerce.number(),
  volume: z.coerce.number(),
  quote_volume: z.coerce.number(),
  trade_count: z.number(),
```

In `alertSchema`, after the `alert_type` line, add

```ts
  severity: z.enum(["LOW", "MEDIUM", "HIGH"]),
  z_score: z.number(),
```

and change the three timestamps (`window_start`, `window_end`, `created_at`) from `z.string().nullable()` to `z.string()`.

- [ ] **Step 2: Update `WsCandle` in `frontend/lib/ws.ts`**

Replace

```ts
  volumeSum: number;
  eventCount: number;
```

with

```ts
  vwap: number;
  volume: number;
  quoteVolume: number;
  tradeCount: number;
```

- [ ] **Step 3: Show USD volume in `CandleTable.tsx`**

Replace `{fmtVolume(c.volume_sum)}` with `{fmtVolume(c.quote_volume)}`, and change the header `<th ...>Vol</th>` text to `Vol (USD)`.

- [ ] **Step 4: Typecheck, lint and build**

```bash
cd frontend
npm ci
npx tsc --noEmit
npm run lint
npm run build
cd ..
```

Expected: all four succeed. If `tsc` reports another usage of a removed field, rename it using the same mapping (`volume_sum→quote_volume` for display, `event_count→trade_count`, `avg_price→vwap`). If `lint` fails only on files this task did not touch, check `git stash; npm run lint; git stash pop` to confirm the failure predates this task, note it in the task report, and continue.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/ws.ts frontend/components/ohlc/CandleTable.tsx
git commit -m "feat(frontend): adopt vwap/volume/quote_volume/trade_count and alert severity

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Delete Streamlit, prune dependencies and dead targets, license, env example, README

**Files:**
- Delete: `src/dashboard/`, `requirements-dashboard.txt`, `src/utils/`, and any Streamlit screenshots not referenced anywhere
- Modify: `Makefile`, `requirements.txt`, `README.md`, and any `docs/*.md` that the grep in Step 6 flags
- Create: `LICENSE`, `frontend/.env.local.example`

- [ ] **Step 1: Delete the dashboard and dead packages**

```bash
grep -rn 'src.utils\|from utils\|src/utils' src scripts tests | grep -v '^src/dashboard' || echo "src/utils unused"
git rm -rq src/dashboard requirements-dashboard.txt src/utils
grep -rn 'dashboard-overview\|dashboard-candlestick' README.md docs || git rm -q docs/screenshots/dashboard-overview.png docs/screenshots/dashboard-candlestick-ma.png
```

Expected: `src/utils unused` is printed before the removal.

- [ ] **Step 2: Prune `requirements.txt`**

```bash
for pkg in requests urllib3 pandas numpy sqlalchemy yaml tenacity structlog pythonjsonlogger; do
  printf "%s: " $pkg; grep -rlE "^\s*(import|from) $pkg" src scripts tests | head -1 || echo "unused"
done
```

For every package reported `unused`, delete its line from `requirements.txt` (the pip names are `requests`, `urllib3`, `pandas`, `numpy`, `SQLAlchemy`, `pyyaml`, `tenacity`, `structlog`, `python-json-logger`). Keep `python-dotenv`, `redis`, `kafka-python-ng`, `websockets`, `pydantic`, `asyncpg`, `pytest`, `pytest-mock` and `httpx`. Then rebuild the venv and re-run the tests:

```bash
rm -rf venv && python3.12 -m venv venv && venv/bin/pip install -q -r requirements.txt -r requirements-api.txt
venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Clean the `Makefile`**

- Delete the targets `setup-dashboard`, `dashboard`, `start-lite`, `consumer` and `run-dashboard`, and the `DC_LITE` variable plus both lines that use it (`$(DC_LITE) down ...` in `stop` and `clean`). `docker-compose-lite.yml` and `simple_consumer.py` do not exist.
- In `setup-all`, change the recipe to `$(PIP) install -r requirements-api.txt`.
- Remove `make dashboard` / `make start-lite` from the header comment and from the `start` target's echo lines.
- In `help`, change the Application Commands pattern to `'^(topics|producer|api|test):.*?## .*$$'`.
- Update `.PHONY` to: `help setup setup-api setup-all start stop status health logs build-flink deploy-flink stop-flink topics producer api test clean`.
- Add this target after `api`:

```make
test: ## Run Python and Flink unit tests
	PYTHONPATH=. $(PYTHON) -m pytest -q
	cd src/flink_jobs && mvn -q test
```

Verify: `make help` prints no errors, and `make -n test` shows both commands.

- [ ] **Step 4: Add `LICENSE`**

Standard MIT text, with the copyright line `Copyright (c) 2026 Zaid Shaikh`:

```text
MIT License

Copyright (c) 2026 Zaid Shaikh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 5: Add `frontend/.env.local.example`**

```text
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Server-side only — do NOT prefix with NEXT_PUBLIC_.
COINGECKO_BASE_URL=https://api.coingecko.com/api/v3
COINGECKO_API_KEY=
```

Check that it is not ignored: `git check-ignore frontend/.env.local.example`. Expected: no output (not ignored). If it is ignored (`frontend/.gitignore` has `.env*`), append `!.env.local.example` to `frontend/.gitignore`.

- [ ] **Step 6: Rewrite the stale README sections and docs**

In `README.md`:

1. Replace the intro paragraph and symbol line with:

```markdown
A streaming data pipeline that ingests **every trade** for 8 crypto pairs from Coinbase's public WebSocket feed, deduplicates and aggregates them into 1-minute OHLCV candles in event time with Apache Flink, flags statistically unusual moves with a z-score detector, and serves the results through FastAPI and a Next.js terminal. TimescaleDB continuous aggregates provide 5-minute, 15-minute and 1-hour rollups.

Tracks `BTC`, `ETH`, `SOL`, `XRP`, `ADA`, `DOGE`, `AVAX`, `POL` (Polygon; `MATIC-USD` is delisted on Coinbase). The list lives in one place: the `cryptocurrencies` table. Runs entirely in Docker.
```

2. Replace the architecture image and the commented-out diagram with this block (drop the outdated PNG reference):

````markdown
```
Coinbase Exchange WebSocket (matches channel, public)
     │  one message per trade
     ▼
Python producer   pydantic validation · trade_id gap tracking · reconnect backoff
     │  Kafka topic crypto-trades (4 partitions, keyed by symbol)
     ▼
Apache Flink      event time from the exchange · 30 s exactly-once checkpoints · RocksDB state
 ├─ Dedup by trade_id (keyed state)
 ├─ raw trades ─────────────► TimescaleDB raw_trades (7-day retention)
 ├─ 1-min OHLCV + VWAP ─────► TimescaleDB price_aggregates_1m ──► continuous aggregates 5m · 15m · 1h
 │                     └────► Redis latest candle + Pub/Sub
 └─ z-score anomaly detector ► TimescaleDB price_alerts
                        └────► Kafka crypto-alerts (transactional, exactly-once)
     │
     ▼
FastAPI (asyncpg + redis.asyncio) ── REST + WebSocket ──► Next.js terminal (:3000)
```
````

3. In the "Key implementation details" table:
   - Delete the rows *Retry / backoff*, *Flink checkpointing*, *Flink state TTL*, *Kafka alert sink*, *PostgreSQL sink* and *Streamlit refresh*.
   - Change *TimescaleDB retention* to `Native add_retention_policy: 7 days for raw_trades, 90 days for candles and rollups`.
   - Keep the *Async API drivers*, *Next.js data fetching* and *Frontend WS resilience* rows.
   - Add these rows:
     - *Checkpointing*: `30 s, EXACTLY_ONCE, RocksDB incremental, retained on cancel, shared flink_data volume`.
     - *Dedup*: `Keyed last-seen trade_id per symbol (DedupByTradeId) + raw_trades primary key`.
     - *Anomaly detection*: `EWMA z-score of 1-min log returns, 30-candle warm-up, |z| > 4, severity bands`.

   Below the table, add a **Delivery guarantees** table (copy the table from spec §2 "Sinks and delivery guarantees") and a **Known limitations** list:

```markdown
### Known limitations

- The producer uses `kafka-python-ng`, which has no idempotent producer; a retried send can duplicate a trade in Kafka. Flink's `DedupByTradeId` and the `raw_trades` primary key remove those duplicates. Upgrade path: `confluent-kafka` with `enable.idempotence=true`.
- A minute with no trades produces no candle (no gap-filling yet).
- `/api/v1/trending` has hourly granularity and stays empty until 24 hours of candles exist.
- Single Kafka broker and single TaskManager: this is a local development topology.
```

4. **Prerequisites:** change Python to `Python 3.11–3.13 (3.12 recommended)`.
5. **Quick Start:**
   - Step 2 becomes `python3.12 -m venv venv && venv/bin/pip install -r requirements.txt -r requirements-api.txt`.
   - Step 3's description now mentions that it creates the `crypto-trades` topic and starts the Coinbase producer.
   - In step 5, delete the Streamlit lines.
   - After the MATIC note, add: "Schema changed in this version (trade-level tables, continuous aggregates). Run `scripts/teardown.sh` once to re-initialise an existing volume."
6. **Web Interfaces:** delete the Streamlit row.
7. **API Endpoints:** `/api/v1/trending` → `Top movers by 24h % change (candles_1h)`, and `/api/v1/symbols` → `Tracked symbols (cryptocurrencies table)`. Replace the paragraph about keeping `SUPPORTED_SYMBOLS` in sync with: "Symbols come from the `cryptocurrencies` table, read by the producer and API at startup and resolved by Flink inside its SQL. Add a symbol by inserting a row (with its `coinbase_product`) and restarting the producer and API."
8. **Environment Variables:** replace the `COINGECKO_API_KEY` row with `KAFKA_TRADES_TOPIC | crypto-trades | Producer topic (older .env files may still say KAFKA_TOPIC; it is ignored)`.
9. **Make Targets:** remove `dashboard`, add `topics` and `test`.
10. **Project Structure:** remove `consumers/` and `dashboard/`, rename the producer file, list the new Flink files (`functions/CandleAggregator.java`, `DedupByTradeId.java`, `ZScoreAnomalyDetector.java`, `sinks/JdbcSinks.java`), remove `utils/CryptoIdMapper.java`, add `tests/`, and change `requirements.txt`'s comment to `Producer + shared + test deps`.

Then run:

```bash
grep -nE 'Streamlit|8501|crypto-prices|crypto_price_producer|MATIC-USD\b.*(tracked|supported)|volume_sum|avg_price|event_count|tenacity|sub-millisecond|SUPPORTED_SYMBOLS|CryptoIdMapper|Chandy' README.md
grep -lnE 'volume_sum|avg_price|event_count|crypto-prices|crypto_price_producer|streamlit|SUPPORTED_SYMBOLS' docs/*.md
```

Expected: the first grep returns nothing. The only allowed hit is the sentence saying MATIC-USD is delisted, which does not match the pattern. For every file the second grep lists, update each hit with the mapping `volume_sum→volume`, `avg_price→vwap`, `event_count→trade_count`, `crypto-prices→crypto-trades`, `crypto_price_producer→coinbase_trades_producer`. Delete Streamlit sections, and replace `SUPPORTED_SYMBOLS` guidance with the `cryptocurrencies` table. Re-run until it lists nothing.

- [ ] **Step 7: Commit**

```bash
git add -A
git status --short   # confirm only intended files: no .env, no graphify-out, no .claude
git commit -m "chore: remove Streamlit and dead targets, prune deps, add LICENSE, rewrite README claims

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: End-to-end acceptance run

This checks spec §7 against the live stack. It needs Docker, network access to Coinbase, and about 40 minutes of wall time.

**Files:**
- Create: `scripts/inject_test_alert.py`

**Interfaces:**
- Consumes: `src.config.KAFKA_PRODUCER_CONFIG`, `KAFKA_TOPIC_TRADES` (Task 3); every earlier task.

- [ ] **Step 1: Create `scripts/inject_test_alert.py`**

```python
"""
Publish a synthetic trade stream for the inactive TEST symbol that ends in a sharp jump,
so the z-score detector must raise exactly one alert.

It runs in real time (~35 minutes) because Flink uses event time and the detector needs
30 one-minute returns of warm-up. Trades are stamped "now", so they flow through the
same watermarks as live Coinbase trades.

Prerequisite (once per database):
  INSERT INTO cryptocurrencies (symbol, name, coingecko_id, coinbase_product, is_active)
  VALUES ('TEST', 'Test Coin', 'test-coin', 'TEST-USD', false) ON CONFLICT DO NOTHING;

Run: PYTHONPATH=. venv/bin/python scripts/inject_test_alert.py
"""

import json
import math
import time
from datetime import datetime, timezone

from kafka import KafkaProducer

from src.config import KAFKA_PRODUCER_CONFIG, KAFKA_TOPIC_TRADES

CALM_MINUTES = 33          # minute 0 anchors; minutes 1-32 give 32 warm-up returns (>= 30)
JUMP_MINUTE = CALM_MINUTES
TOTAL_MINUTES = CALM_MINUTES + 2   # + the jump minute + one trailing minute to close its window
TRADES_PER_MINUTE = 12     # one every 5 s; the detector needs >= 5 per candle


def utc_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> None:
    producer = KafkaProducer(**KAFKA_PRODUCER_CONFIG)
    trade_id = int(time.time()) * 1000   # stays above ids from earlier runs (DedupByTradeId state)
    price = 100.0
    start = math.ceil(time.time() / 60) * 60   # next minute boundary
    time.sleep(start - time.time())

    for minute in range(TOTAL_MINUTES):
        if minute == JUMP_MINUTE:
            price *= math.exp(0.05)
        elif minute > 0:
            price *= math.exp(0.001 if minute % 2 else -0.001)
        for i in range(TRADES_PER_MINUTE):
            time.sleep(max(0.0, start + minute * 60 + i * 5 - time.time()))
            trade_id += 1
            now = utc_z(datetime.now(timezone.utc))
            producer.send(KAFKA_TOPIC_TRADES, key="TEST", value=json.dumps({
                "trade_id": trade_id, "symbol": "TEST", "price": f"{price:.8f}", "size": "0.01",
                "side": "buy", "sequence": trade_id, "event_time": now, "ingest_time": now,
            }))
        print(f"minute {minute:2d}/{TOTAL_MINUTES - 1}: price {price:.6f}", flush=True)

    producer.flush()
    print("done: expect exactly one PRICE_SPIKE alert for TEST")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Reset and start the stack**

> **Destructive:** `teardown.sh` deletes all Docker volumes for this project (local Postgres, Kafka and Flink data). Confirm with the user before running it.

```bash
bash scripts/teardown.sh
bash scripts/start_pipeline.sh          # creates crypto-trades (4 partitions) and starts the producer
make build-flink deploy-flink
(PYTHONPATH=. venv/bin/python -m uvicorn src.api.main:app --port 8000 > /tmp/api.log 2>&1 &)
docker exec -i postgres psql -U "${POSTGRES_USER:-crypto_user}" -d "${POSTGRES_DB:-crypto_db}" -c \
  "INSERT INTO cryptocurrencies (symbol, name, coingecko_id, coinbase_product, is_active)
   VALUES ('TEST', 'Test Coin', 'test-coin', 'TEST-USD', false) ON CONFLICT DO NOTHING;"
(PYTHONPATH=. venv/bin/python scripts/inject_test_alert.py > /tmp/inject.log 2>&1 &)
```

Check immediately:

```bash
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --describe --topic crypto-trades | head -1
curl -s localhost:8082/jobs/overview | python3 -m json.tool | grep -E '"state"|"name"'
```

Expected: `PartitionCount: 4`, and the job `Crypto trades -> OHLCV + z-score alerts` in state `RUNNING`.

- [ ] **Step 3: Wait about 36 minutes, until `/tmp/inject.log` ends with `done: ...`, then check criteria 1–3**

```bash
PSQL='docker exec -i postgres psql -U crypto_user -d crypto_db -At -c'
$PSQL "SELECT count(*) FROM raw_trades;"                                   # criterion 1: > 0 and growing
sleep 30; $PSQL "SELECT count(*) FROM raw_trades;"
$PSQL "SELECT count(*) FROM (SELECT crypto_id, trade_id FROM raw_trades GROUP BY 1,2 HAVING count(*) > 1) d;"   # expect 0
$PSQL "SELECT count(*) FROM price_aggregates_1m WHERE trade_count <= 0 OR vwap < low_price OR vwap > high_price;" # criterion 2: expect 0
$PSQL "SELECT count(*) FROM price_aggregates_1m;"                           # > 0
$PSQL "SELECT (SELECT count(*) FROM candles_5m), (SELECT count(*) FROM candles_15m);"   # criterion 3: both > 0
$PSQL "CALL refresh_continuous_aggregate('candles_1h', NULL, NULL);" ; $PSQL "SELECT count(*) FROM candles_1h;"  # > 0
```

(`candles_1h`'s policy only materializes closed hours, which is why it gets a manual refresh here.)

- [ ] **Step 4: Criterion 4, the alert in Postgres, the API and the transactional Kafka topic**

```bash
$PSQL "SELECT alert_type, severity, z_score FROM price_alerts pa JOIN cryptocurrencies c ON c.id = pa.crypto_id WHERE c.symbol = 'TEST';"
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic crypto-alerts \
  --from-beginning --isolation-level read_committed --timeout-ms 15000 | grep '"symbol":"TEST"'
curl -s "localhost:8000/api/v1/alerts/ALL?hours=2" | python3 -m json.tool | grep -c '"TEST"'
```

Expected: exactly one `PRICE_SPIKE | HIGH | <z>` row, exactly one TEST line from Kafka, and a count ≥ 1 from the API. TEST is inactive, so `/alerts/ALL` still returns it (the SQL filters by symbol, not `is_active`). That's fine for this check.

- [ ] **Step 5: Criterion 5, the Redis flush fallback**

```bash
curl -si localhost:8000/api/v1/latest/BTC | grep -i x-data-source      # redis
docker exec redis redis-cli FLUSHALL
curl -si localhost:8000/api/v1/latest/BTC | grep -iE '^HTTP|x-data-source'   # HTTP/1.1 200, postgres
```

- [ ] **Step 6: Criterion 6, TaskManager restart recovery and shared checkpoints**

```bash
docker exec flink-jobmanager ls /opt/flink/data/checkpoints/*/ | grep chk-   # checkpoints on the shared volume
docker restart flink-taskmanager
for i in $(seq 1 24); do
  state=$(curl -s localhost:8082/jobs/overview | python3 -c 'import sys,json;print(json.load(sys.stdin)["jobs"][0]["state"])')
  echo "$i $state"; [ "$state" = RUNNING ] && break; sleep 10
done
curl -s localhost:8082/jobs/overview | python3 -c 'import sys,json;j=json.load(sys.stdin)["jobs"][0];print(j["state"])'
```

Expected: at least one `chk-N` directory, and the job back in `RUNNING` within 4 minutes without manual action. Afterwards, re-run the duplicate query from Step 3 and expect `0`.

- [ ] **Step 7: Criterion 7, the unit tests**

Run: `make test`
Expected: pytest and Maven both pass.

- [ ] **Step 8: Clean up the TEST fixture data**

```bash
$PSQL "DELETE FROM price_alerts WHERE crypto_id = (SELECT id FROM cryptocurrencies WHERE symbol='TEST');
       DELETE FROM price_aggregates_1m WHERE crypto_id = (SELECT id FROM cryptocurrencies WHERE symbol='TEST');
       DELETE FROM raw_trades WHERE crypto_id = (SELECT id FROM cryptocurrencies WHERE symbol='TEST');"
```

(The TEST row in `cryptocurrencies` stays, inactive, so the injector can be re-run.)

- [ ] **Step 9: Record the results and commit**

Append a short `## Acceptance run (<date>)` section to the spec with the observed numbers: raw_trades count after 30 min, candle count, the TEST alert's z-score, and the TaskManager recovery time in seconds.

```bash
git add scripts/inject_test_alert.py docs/superpowers/specs/2026-09-25-real-ingestion-and-correctness-design.md
git commit -m "test: end-to-end acceptance run with synthetic alert injection

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
