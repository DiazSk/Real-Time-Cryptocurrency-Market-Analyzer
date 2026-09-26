# Sub-project 1: Real Ingestion + Correctness — Design

**Date:** 2026-09-25
**Status:** Draft for review
**Branch:** `feat/real-ingestion-correctness`

## Context and goal

The project is on the owner's resume for Data Engineer roles (primary), with Analytics Engineer / Data Analyst as secondary targets. An audit found that the architecture is real but several outputs and claims are not:

- Nothing writes to `price_alerts` or `raw_price_data`, so `/alerts` and `/trending` always return empty.
- The Kafka `EXACTLY_ONCE` alert sink has no `transactionalIdPrefix` and uses the default 1 h transaction timeout (the broker maximum is 15 min). It is probably misconfigured.
- CoinGecko is polled every 5 s but refreshes about every 60 s. As a result `volume_sum` (a sum of 24 h volume snapshots) and `trade_count` (a count of polls) mean nothing, and "event time" is really poll time.
- The anomaly rule (a >5% move within one 1-min candle) almost never fires for large caps.
- A Redis cache miss returns 404 instead of falling back to TimescaleDB.
- The checkpoint interval is 60 s, but the resume says 30 s.
- The README has an MIT license badge but there is no LICENSE file, and the documented `frontend/.env.local.example` does not exist.
- The symbol list is hard-coded in 4 places.

This sub-project makes the pipeline process **real trade data correctly**, so that every guarantee described in the README is true. Proving those guarantees with automated tests and benchmarks is sub-project 2.

### Roadmap (each sub-project gets its own spec)

1. **Real ingestion + correctness** (this doc)
2. Proof harness: pytest/Flink tests in CI, record/replay load test (p95 latency, throughput), chaos test for exactly-once, measured numbers in the README
3. Analytics layer: Coinbase historical candle backfill, dbt (staging → marts) on TimescaleDB with tests and docs
4. Written analysis: 2–3 questions answered with charts (for example volatility clustering, alert precision)

## Verified external facts (2026-09-25)

- `wss://ws-feed.exchange.coinbase.com`, channel `matches`: public, no auth. One message per trade with `trade_id`, `sequence`, `price`, `size`, `side`, `time`, `product_id`. Observed about 10 trades/s across the 8 products on a quiet night.
- `MATIC-USD` is **delisted** on Coinbase. `POL-USD` is online, so the symbol set becomes BTC, ETH, SOL, XRP, ADA, DOGE, AVAX, **POL**.
- `GET https://api.exchange.coinbase.com/products/{id}/candles?granularity=60` returns up to about 300 candles per call, with no auth. This is used by sub-project 3.

## Corrections found while planning (2026-09-25)

These override the sections below where they conflict.

1. **Gap detection uses `trade_id`, not `sequence`.** A 25 s probe showed `sequence` jumping by 2–99+ between consecutive matches of one product, because it is shared with order-book events the `matches` channel doesn't carry. `trade_id` went up by exactly 1 in all 133 cases. `sequence` is still stored in `raw_trades`.
2. **Flink dedups trades before windowing.** `DedupByTradeId` keeps the last `trade_id` per symbol in keyed state and drops anything not newer. Without it, a producer retry duplicate would inflate candle volume, not just `raw_trades`. This is correct because the producer keeps per-partition order (`max_in_flight_requests_per_connection=1`).
3. **The JobManager never loads `configs/flink-conf.yaml`.** Only the TaskManager mounts it. As a result the RocksDB backend, exponential-delay restarts and `state.checkpoints.dir` in that file do not apply to the job, and the code sends checkpoints to `file:///opt/flink/checkpoints`, which is not on the shared `flink_data` volume. Fix: put the job-level settings in the JobManager's `FLINK_PROPERTIES` and drop `setCheckpointStorage(...)` from the code.
4. **Reconnects use a plain backoff loop** that resets after a connection has been healthy for 60 s. `tenacity` is removed because nothing else uses it.
5. **The alert JSON fields `open_price`/`close_price` become `old_price`/`new_price`** (the previous close and this close), matching the `price_alerts` columns.
6. **Acceptance criterion 4's fixture** is `scripts/inject_test_alert.py`. It publishes synthetic trades for an inactive `TEST` symbol in real time for about 35 minutes (warm-up needs 30 one-minute returns in event time), ending in a +5% jump.
7. **Stale `KAFKA_TOPIC=crypto-prices` in existing `.env` files:** the producer reads a new variable, `KAFKA_TRADES_TOPIC` (default `crypto-trades`).

## 1. Ingestion

### Symbol source of truth

The `cryptocurrencies` table is the only symbol list. It gains a `coinbase_product VARCHAR(20) UNIQUE NOT NULL` column (for example `BTC-USD`). The existing `coingecko_id` stays; the frontend uses it for coin-detail slugs (POL → `polygon-ecosystem-token`).

- The producer and the API read the table at startup.
- Flink resolves `crypto_id` inside SQL with `(SELECT id FROM cryptocurrencies WHERE symbol = ?)`. `CryptoIdMapper.java` is deleted.
- `CRYPTO_IDS` in `src/config.py` and `SUPPORTED_SYMBOLS` / `SYMBOL_METADATA` in `src/api/config.py` are removed.

### Producer: `src/producers/coinbase_trades_producer.py`

Replaces `crypto_price_producer.py`.

- Subscribes to `matches` for every `coinbase_product` in the table.
- Validates each message into a Pydantic `Trade` model: `trade_id:int, symbol:str, price:Decimal>0, size:Decimal>0, side:Literal['buy','sell'], sequence:int, event_time:datetime (exchange time), ingest_time:datetime (producer clock, UTC)`. Invalid messages are logged and counted, then dropped.
- Publishes the JSON to the topic `crypto-trades` with key = symbol.
- Kafka config: `acks=all`, `max_in_flight_requests_per_connection=1`, `retries` > 0.
  - `kafka-python-ng` has no idempotent producer, so a retry can create a duplicate message. These duplicates are absorbed downstream by `trade_id` dedup (see §2). The upgrade path is `confluent-kafka` with `enable.idempotence=true`; this limitation is documented in the README.
- **Reconnect:** `tenacity` exponential backoff with jitter on disconnect and on connect failure. The producer resubscribes after reconnecting.
- **Gap detection:** the producer tracks the last `sequence` for each product. A jump greater than 1 logs a warning and increments a `sequence_gaps` counter. Counters (messages, invalid, gaps, reconnects) are logged every 60 s.
- `event_time` drives Flink event time. `ingest_time - event_time` is the ingestion-lag metric that sub-project 2 will report.
- The producer is asyncio-based (because `websockets` is). It loads the symbol list once at startup with `asyncpg`; a missing or empty table is a fatal startup error.
- New dependency: `websockets` (added to `requirements.txt`). `pydantic` and `asyncpg` move from `requirements-api.txt` to `requirements.txt`.

### Topic

`scripts/start_pipeline.sh` creates `crypto-trades` with 4 partitions (to match `FLINK_PARALLELISM`) using `kafka-topics --create --if-not-exists`, before the producer starts. The `crypto-prices` topic is no longer used.

### Removed

`src/producers/crypto_price_producer.py`, the CoinGecko constants in `src/config.py`, the `raw_price_data` table, and the `v_latest_prices` / `v_price_stats_24h` views.

## 2. Flink job

### Source and time

- The `Trade` POJO replaces `PriceUpdate`.
- The Kafka source uses `OffsetsInitializer.committedOffsets(OffsetResetStrategy.EARLIEST)`.
- Watermarks: `forBoundedOutOfOrderness(2s)`, timestamp = `event_time`, `withIdleness(30s)`.
- Windows use `allowedLateness(0)`. Late trades go to a side output that increments a Flink counter metric (`lateTrades`), so they are counted rather than silently dropped.

### 1-minute OHLCV (`OHLCAggregator` rewrite)

- `open` = price of the trade with the minimum `event_time`, and `close` = price with the maximum `event_time`. Ties are broken by `trade_id`. This fixes the current bug where open/close come from arrival order.
- `high` / `low` = max / min price.
- `volume` = Σ size, `quote_volume` = Σ price·size, `vwap` = quote_volume / volume, `trade_count` = number of trades.
- `merge()` stays correct under the same rules.
- A minute with no trades produces no candle. This is documented, and gap-filling is a dbt concern (sub-project 3).

### 5/15/60-minute rollups

The Flink 5- and 15-minute windows (currently only printed to stdout) are deleted. They are replaced by TimescaleDB continuous aggregates `candles_5m`, `candles_15m` and `candles_1h` over `price_aggregates_1m`:

- `first(open, window_start)`, `max(high)`, `min(low)`, `last(close, window_start)`, `sum(volume)`, `sum(quote_volume)`, `sum(trade_count)`, with vwap = sum(quote_volume) / sum(volume).
- Each has a refresh policy (for example every 1 min for 5m, 5 min for 15m, 15 min for 1h).

### Sinks and delivery guarantees

| Sink | Mechanism | Guarantee |
|---|---|---|
| `raw_trades` hypertable | JDBC batch, `ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING` | At-least-once delivery with idempotent writes, so effectively-once |
| `price_aggregates_1m` | JDBC upsert on `(crypto_id, window_start)` | Effectively-once |
| `price_alerts` (**new**) | JDBC, unique `(crypto_id, window_start, alert_type)`, `DO NOTHING` | Effectively-once |
| Kafka `crypto-alerts` | `KafkaSink` `EXACTLY_ONCE`, `setTransactionalIdPrefix("crypto-alerts")`, producer property `transaction.timeout.ms=900000` | Exactly-once for `read_committed` consumers; visibility is delayed by up to one checkpoint interval |
| Redis `crypto:{SYM}:latest` + Pub/Sub `crypto:updates` | `SETEX` + `PUBLISH` | At-least-once. The overwrite is idempotent; clients dedupe on `window_start` |

- The Kafka alert topic is kept on purpose: sub-project 2's chaos test consumes it with `read_committed` to prove the exactly-once guarantee.
- `src/consumers/alert_consumer.py` is deleted.
- **Checkpointing:** 30 s, `EXACTLY_ONCE`, retained on cancellation, set **only in code**. `execution.checkpointing.interval` is removed from `configs/flink-conf.yaml`.
- Remove the comment claiming the JDBC sink takes part in two-phase commit.

### Anomaly detection (`AnomalyDetector` rewrite)

- Keyed by symbol, over 1-minute candles. State: an EWMA mean and variance of log returns `ln(close_t / close_{t-1})` (α = 2/(60+1), roughly a 60-candle span), the previous close, the number of candles seen, and the last alerted window.
- z = (r − mean) / sqrt(var). Emit an alert when `candles_seen ≥ 30`, `trade_count ≥ 5` and `|z| > 4`.
  - Type: `PRICE_SPIKE` if r > 0, otherwise `PRICE_DROP`.
  - Severity: LOW for 4 ≤ |z| < 6, MEDIUM for 6 ≤ |z| < 8, HIGH for |z| ≥ 8.
- The state update happens **after** scoring, so an outlier does not mask itself.
- The existing 1 h state TTL is kept.
- `PriceAlert` gains `zScore` and `severity`. `price_alerts` gains `z_score DECIMAL(10,4)`, and `severity` becomes a CHECK constraint over (LOW, MEDIUM, HIGH).
- The thresholds (30, 5, 4, 60) are constants in the class. They are not made configurable until sub-project 4 has evaluated them.

## 3. Schema (`configs/init-db.sql` rewrite)

- `cryptocurrencies`: add `coinbase_product`. Seed the 8 symbols, with POL replacing MATIC.
- `raw_trades` hypertable on `event_time`: `crypto_id, trade_id BIGINT, price DECIMAL(20,8), size DECIMAL(28,10), side VARCHAR(4), sequence BIGINT, event_time TIMESTAMPTZ, ingest_time TIMESTAMPTZ`, with PK `(crypto_id, trade_id, event_time)`. 7-day retention.
- `price_aggregates_1m`: rename `avg_price → vwap` and `volume_sum → volume` (DECIMAL(28,10)), add `quote_volume DECIMAL(28,8)`. Keep `trade_count`. 90-day retention.
- Continuous aggregates `candles_5m`, `candles_15m`, `candles_1h`, each with a refresh policy and 90-day retention.
- `price_alerts`: add `z_score` and the unique constraint above, and add the severity CHECK.
- Drop `raw_price_data`, `processing_metadata`, `v_latest_prices` and `v_price_stats_24h`.
- Timestamps become `TIMESTAMPTZ` throughout.
- No migration tool. The README instructs `scripts/teardown.sh` for existing volumes.

## 4. API and frontend contract

- `/api/v1/latest/{symbol}` and `/latest/all`: on a Redis miss, read the newest row from `price_aggregates_1m` and set `X-Data-Source: postgres`. Keep `X-Data-Source: redis` on a hit. Return 404 only if both are empty.
- `/api/v1/trending`: compares the latest close in `candles_1h` with the close 24 h earlier for each symbol, and keeps the `abs|gainers|losers` sorting.
- `/api/v1/symbols`: served from `app.state.symbols`, which is loaded from `cryptocurrencies` in the lifespan hook. Other endpoints validate symbols against the same set.
- `/api/v1/alerts`: responses include `z_score` and `severity`.
- **Field renames across the stack:** `avg_price→vwap`, `volume_sum→volume`, `event_count→trade_count`, plus a new `quote_volume`. Applied in `src/api/models.py`, `src/api/endpoints/{latest,historical}.py`, `frontend/lib/types.ts`, and every frontend component that reads them. The API is not versioned because it has no external consumers.

## 5. Cleanup

- Delete the Streamlit dashboard: `src/dashboard/`, `requirements-dashboard.txt`, the `make dashboard` target, and the Streamlit mentions in the README.
- Add an MIT `LICENSE` in the owner's name, and `frontend/.env.local.example`.
- `make producer` runs the new producer.
- README:
  - Update the architecture section.
  - Add the delivery-guarantee table from §2.
  - Document POL.
  - Remove every performance claim that has not been measured (sub-project 2 adds measured ones).
  - Remove the `CryptoIdMapper` sync note.

## 6. Testing

In scope here:

- **Java (JUnit 5 + Flink test utilities):**
  - `OHLCAggregator`: out-of-order trades produce the correct open/close, VWAP math, and merge equivalence.
  - `AnomalyDetector` via `KeyedOneInputStreamOperatorTestHarness`: no alerts during warm-up, fires at |z| > 4, does not fire below `trade_count` 5, severity bands, and no duplicate alert for the same window.
- **Python (pytest):**
  - `Trade` validation: good and bad messages.
  - Sequence-gap counter.
  - `/latest` fallback path, using a fake Redis miss and the asyncpg fixture pattern chosen in the plan.

Out of scope here: CI, load tests, chaos tests (all sub-project 2).

## 7. Acceptance criteria (checked manually after 30 min of running the stack)

1. `raw_trades` row count grows, and `SELECT trade_id, crypto_id, count(*) … HAVING count(*) > 1` returns 0 rows.
2. Every `price_aggregates_1m` row has `trade_count > 0` and `low_price ≤ vwap ≤ high_price`.
3. `candles_5m`, `candles_15m` and `candles_1h` return rows.
4. An alert produced through a test fixture (a candle stream that crosses the threshold) appears both in `/api/v1/alerts` and in a `read_committed` read of `crypto-alerts`.
5. After `redis-cli FLUSHALL`, `/api/v1/latest/BTC` returns 200 with `X-Data-Source: postgres`.
6. After `docker restart flink-taskmanager`, the job returns to RUNNING without manual action.
7. All unit tests in §6 pass.

## Out of scope

CoinGecko-backed frontend pages (unchanged), CI, benchmarks, dbt, backfill, schema registry/Avro, cloud deployment, auth.

## Acceptance run (2026-09-26)

Ran against a freshly torn-down and rebuilt local stack (`scripts/teardown.sh` then `scripts/start_pipeline.sh`, Maven-built Flink job deployed via `make build-flink deploy-flink`), plus `scripts/inject_test_alert.py` publishing a synthetic 35-minute TEST trade stream that ends in a sharp jump. One environment fix was required before the job would start: the `flink_data` named Docker volume was created `root:root` by Docker after teardown, and the `flink` user inside the containers could not write `/opt/flink/data/checkpoints`, so the first `deploy-flink` submission failed with `IOException: Failed to create directory for shared state`. Fixed at the time with a manual `docker exec -u root flink-jobmanager chown -R flink:flink /opt/flink/data` before resubmitting; the second submission (JobID `397f19af8a705cbf43bdccc920cb79fc`) ran for the remainder of the test. This — plus a second issue where the TaskManager's bind-mounted `configs/flink-conf.yaml` got rewritten in place by `/docker-entrypoint.sh` on every `docker compose up` — is now fixed permanently in `docker-compose.yml` (commit "fix(infra): own the Flink data volume and stop rewriting the repo flink-conf.yaml"): both the `jobmanager` and `taskmanager` services now override `entrypoint`/`command` to `chown -R flink:flink /opt/flink/data` before starting, and `taskmanager` mounts the repo file read-only at `/opt/flink/conf-src/flink-conf.yaml` and copies it into `/opt/flink/conf/flink-conf.yaml` inside the container before the entrypoint mutates it, so the host file is never touched.

| # | Criterion | Result | Observed |
|---|-----------|--------|----------|
| 1 | `raw_trades` grows, 0 duplicates | PASS | `raw_trades` count 17,847 at 06:56:11Z → 18,009 at 06:56:29Z (growing); duplicate query (`crypto_id, trade_id` group-by having count>1) = 0 |
| 2 | Every `price_aggregates_1m` row has `trade_count > 0` and `low_price ≤ vwap ≤ high_price` | PASS | bad-candle count = 0; `price_aggregates_1m` row count = 323 |
| 3 | `candles_5m`, `candles_15m`, `candles_1h` all return rows | PASS | `candles_5m` = 62, `candles_15m` = 9, `candles_1h` = 9 (after manual `refresh_continuous_aggregate`) |
| 4 | TEST alert appears in Postgres, `crypto-alerts` (read_committed), and the API | PASS | `price_alerts`: exactly one row, `PRICE_SPIKE \| HIGH \| z_score 63.3248`; Kafka `crypto-alerts` read_committed consumer returned exactly one `"symbol":"TEST"` line (`z_score 63.32484600102509`, `price_change_percent 5.1271`, window `06:54:00Z`–`06:55:00Z`); `GET /api/v1/alerts/ALL?hours=2` contained 1 `"TEST"` match |
| 5 | Redis flush fallback | PASS | `/api/v1/latest/BTC` returned `x-data-source: redis` before `FLUSHALL`; `HTTP/1.1 200 OK` and `x-data-source: postgres` after |
| 6 | TaskManager restart recovery, shared checkpoints | PASS | `chk-73` present under `/opt/flink/data/checkpoints/<job-id>/` before restart; `docker restart flink-taskmanager` issued at 06:57:05Z; job observed `RUNNING` again at 06:57:20Z (≈15s, well under the 4-minute budget); duplicate-row query re-run after recovery = 0 |
| 7 | Unit tests pass | PASS | `make test`: pytest `35 passed, 5 warnings in 0.33s`; `mvn -q test` (Flink/JUnit) completed with no failures reported — `src/flink_jobs/target/surefire-reports` show 21 Java tests, 0 failures (`TradeDeserializerTest` 6, `CandleAggregatorTest` 5, `DedupByTradeIdTest` 1, `ZScoreAnomalyDetectorTest` 9) |

Additional measurements:
- Producer stats (last line captured before cleanup, `/tmp` redirected from `scripts/start_pipeline.sh`, timestamps in local time): `2026-09-25 23:57:32,768 stats {'published': 17969, 'invalid': 0, 'duplicates': 0, 'send_errors': 0, 'reconnects': 0} missed_trades=0`. Producer had been running since 23:19:26 local time and was left running at the user's request (~38 minutes elapsed at last sample).
- Flink Kryo/POJO fallback check: `docker logs flink-jobmanager` and `docker logs flink-taskmanager` grepped for `cannot be used as a POJO|GenericType|Kryo` at two points (after ~10 minutes and again after ~38 minutes of runtime) — no matches either time.
- TEST fixture rows (`price_alerts`, `price_aggregates_1m`, `raw_trades` for the TEST crypto_id) were deleted per the brief's Step 8; the `cryptocurrencies` row for TEST (`is_active = false`) was left in place for future re-runs.
