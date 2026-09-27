# Sub-project 3: Analytics Layer (backfill + dbt + Airflow) — Design

**Date:** 2026-09-27
**Status:** Approved in chat (the owner pre-approved the spec and asked for implementation to start right away)
**Branch:** `feat/analytics-layer`

## Context and goal

The pipeline produces correct 1-minute candles and alerts. Sub-project 2 measured its guarantees. Nothing yet shows **analytics-engineering** skills: modeling, testing, documentation, lineage, and orchestration.

This sub-project adds:

1. A **backfill**: 90 days of official Coinbase 1-minute candles, plus exact repair of trade gaps by trade ID. The gaps come from producer restarts; the chaos run counted 1.
2. A **dbt project**: staging → intermediate → marts. Each mart answers one question for sub-project 4 (the written analysis), and one mart compares the pipeline against the exchange.
3. An **Airflow DAG**: runs backfill → gap repair → dbt build every hour, with each dbt model visible as its own task (Astronomer Cosmos).

**Decisions made in chat:**

- **Marts** serve sub-project 4's questions (option A), plus a data-quality mart comparing the pipeline with the exchange.
- **History depth:** 90 days, about 1.04 M candles.
- **Orchestration:** Airflow, chosen by the owner over plain `make` targets and over Dagster, as the industry-standard tool.

**Success means:**

- `make backfill` loads 90 days, and a re-run adds nothing new.
- After a producer-restart gap, `make backfill` repairs it, and `chaos_gaps` returns 0 for that window.
- `make dbt` passes every model, generic test, singular test, and unit test on real data.
- CI runs `dbt build` against fixture data and rejects any DAG import error.
- The DAG runs green in the Airflow UI.
- The README reports the measured numbers.

## Verified external facts (2026-09-27)

- **Candles:** `GET https://api.exchange.coinbase.com/products/{id}/candles?granularity=60&start=<ISO>&end=<ISO>`, public.
  - Rows come back as `[time, low, high, open, close, volume]`, newest first, at most 300 per request.
  - `time` is the bucket start in epoch seconds. Minutes with no trades are omitted.
- **Trades:** `GET https://api.exchange.coinbase.com/products/{id}/trades?limit=1000&after=<trade_id>`, public.
  - Returns trades with `trade_id < after`, newest first, as objects with `trade_id`, `side`, `size`, `price` and `time`.
  - The `cb-after` response header holds the oldest `trade_id` in the page and is the cursor for the next page.
  - There is no `sequence` field.
  - `side` is the maker's side, the same meaning as on the `matches` channel, so repaired rows store it unchanged. Implementation checks this against live data: for trade ids present in both `raw_trades` and a REST page, `side` must match.
- **Public rate limit:** about 10 requests/s per IP. We use 5/s.
- **Versions:**
  - `apache-airflow` 3.3.2 (Python >= 3.10);
  - `astronomer-cosmos` 1.15.1 (requires `apache-airflow >= 2.9`);
  - `dbt-core` 1.12.5 and `dbt-postgres` 1.11.0 (Python >= 3.10).
- **Environment check:** a dry-run install of dbt into the main venv changes none of the pinned packages. `pydantic` stays at 2.10.3; the only new shared package is `protobuf` 6.33. dbt therefore goes in the main venv, and no `.venv-dbt` is needed.

## Section 1: Backfill — `src/backfill/`, run with `make backfill`

### Schema: `configs/migrations/001_analytics.sql` (idempotent)

- **New table `coinbase_candles_1m`:**
  - `crypto_id INT REFERENCES cryptocurrencies(id)`, `bucket TIMESTAMPTZ`;
  - `open, high, low, close DECIMAL(20,8)`, `volume DECIMAL(28,10)`;
  - `loaded_at TIMESTAMPTZ DEFAULT now()`, with `PRIMARY KEY (crypto_id, bucket)`;
  - a hypertable on `bucket` with 7-day chunks and a retention policy of 120 days, so the 90-day history keeps some headroom.
- **`raw_trades` changes:**
  - `ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'stream'` with a check `IN ('stream', 'rest_backfill')`;
  - `ALTER COLUMN sequence DROP NOT NULL`.
  - Existing inserts name their columns, so the Flink sink and the lite consumer are unaffected.
- **Applied three ways:**
  - `make migrate` runs it on existing volumes;
  - `docker-compose.yml` mounts it into `/docker-entrypoint-initdb.d/` as `002_analytics.sql`, so it runs after `init-db.sql` on fresh volumes;
  - the CI `schema` job runs it before the checks.

### Candle backfill (`src/backfill/candles.py`)

- **Which symbols:** the active symbols in `cryptocurrencies`, each mapped to its `coinbase_product`.
- **Where each symbol starts:** `max(bucket)` minus 1 minute, which re-fetches the last, possibly partial, minute. When the table is empty for a symbol, it starts 90 days ago.
- **Windows:** fixed 300-minute windows from there to now. This is a pure function, `candle_windows(start, end)`, which yields `(start, end)` pairs.
- **Writes:** each window is fetched and upserted with `ON CONFLICT (crypto_id, bucket) DO UPDATE`, so a partial minute gets corrected on the next run.
- **HTTP:** one `httpx.Client` with a 10 s timeout. Requests are throttled to 5/s. A 429 or 5xx response is retried with exponential backoff (1 s up to 30 s, 5 attempts). A 4xx other than 429 is raised.
- **Logging:** one summary line per symbol.

### Trade-gap repair (`src/backfill/trade_gaps.py`)

1. **Find gaps.** SQL over `raw_trades` for the last 7 days (the retention period), per `crypto_id`, ordered by `trade_id`: rows where `trade_id − lag(trade_id) > 1`. Each gap is returned as `(crypto_id, symbol, product, prev_id, next_id)`, meaning the ids from `prev_id + 1` to `next_id − 1` are missing.
2. **Guards.** A gap with more than 10,000 missing ids is logged and skipped, never half-repaired.
3. **Fetch.** Page with `after=next_id` and then `after=<cb-after>`, collecting trades whose `prev_id < trade_id < next_id`, and stop once a page reaches `trade_id <= prev_id + 1`. The pure function `select_missing(page, prev_id, next_id)` filters one page.
4. **Insert** into `raw_trades` with:
   - `source = 'rest_backfill'` and `sequence = NULL`;
   - `event_time` from the trade's `time`, and `ingest_time = now()`;
   - `ON CONFLICT DO NOTHING`.
5. **Recompute candles.** For every minute that received a repaired trade, recompute its `price_aggregates_1m` row from `raw_trades`, using the lite consumer's recompute SQL. That SQL is moved into a shared module, `src/candle_sql.py`, and both callers import it, so it isn't copied. The continuous aggregates pick up the change on their next refresh.
6. **Report.** Returns `{gaps_found, gaps_repaired, gaps_skipped, trades_inserted, minutes_recomputed}` and logs it.

### Entry point

`python -m src.backfill [candles|gaps|all]`, with a default of `all`, run by `make backfill`. Airflow calls the two sub-commands as separate tasks.

### Tests (pytest, no network)

- **Pure functions:**
  - `candle_windows` covers an exact multiple, a remainder, and `start >= end` (no windows);
  - `select_missing` covers the boundaries, which are exclusive;
  - parsing a candle row.
- **One integration-style test with `httpx.MockTransport`:** a gap of 2 fetches exactly 2 trades across 2 pages, then produces the insert rows (source, unchanged side, NULL sequence) and exactly 1 minute to recompute. The DB layer is a small fake.

## Section 2: dbt project — `analytics/`

- **Packages:** `dbt-core` 1.12.5, `dbt-postgres` 1.11.0, `dbt_utils`.
- **`profiles.yml`** is committed and reads `env_var('POSTGRES_HOST', 'localhost')` and the other connection settings, so no secrets are committed. There are two targets: `dev` (the default) and `ci`.
- **Materializations:**
  - staging and intermediate are views;
  - `fct_candles_1m` is incremental (`unique_key=['crypto_id', 'bucket']`), and each run reprocesses the last 2 hours;
  - marts are tables.

### Sources (`models/staging/sources.yml`)

- **Tables:** `cryptocurrencies`, `raw_trades`, `price_aggregates_1m`, `coinbase_candles_1m`, `price_alerts`.
- **Freshness:** set on `price_aggregates_1m` (`window_end`: warn 10 min, error 1 h) and on `coinbase_candles_1m` (`bucket`: warn 2 h, error 1 day).

### Staging

These models only rename, cast and filter.
- `stg_symbols`
- `stg_trades`
- `stg_pipeline_candles` (`bucket = window_start`)
- `stg_exchange_candles`
- `stg_alerts`

### Intermediate

- **`int_candles_unified`:** a full outer join of pipeline and exchange candles on `(crypto_id, bucket)`.
  - OHLCV is taken from the pipeline when present, otherwise from the exchange.
  - `source` is `'pipeline'` or `'exchange'`.
  - Both closes and both volumes are kept for reconciliation.
- **`int_returns_1m`:** `ln(close / prev_close)`, but only when the previous row is exactly 1 minute earlier; otherwise it's NULL.

### Marts

| Model | Grain | Logic |
|---|---|---|
| `fct_candles_1m` | symbol-minute | The unified candles plus the return; incremental |
| `mart_volatility_hourly` | symbol-hour | `realized_vol = sqrt(sum(r²))`, `n_minutes`, `prev_hour_vol` (lag). This is the input for clustering |
| `mart_seasonality` | symbol × ISO weekday × UTC hour | Average `realized_vol`, average hourly volume, `n_hours` |
| `mart_signals` | symbol-minute where \|z\| > 4 | `z = (r − mean_60) / stddev_60` over the previous 60 returns (`ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING`). At least 30 prior returns are required (warm-up), plus `volume > 0`. Severity uses Flink's bands: LOW 4–6, MEDIUM 6–8, HIGH ≥ 8. Direction comes from the sign of `r`. Forward log returns at +5, +15 and +60 min; `continued_15m = sign(fwd_15) = sign(r)`. `flink_alert` is true when `price_alerts` has a row for the same symbol and minute |
| `mart_signal_precision` | symbol × severity | `n_signals`, `pct_continued_15m`, `pct_continued_60m`, `n_flink_matched` |
| `mart_pipeline_vs_exchange` | symbol-minute where both candles exist | `close_diff_pct`, `volume_ratio`, and `agrees = abs(close_diff_pct) <= 0.05 AND abs(volume_ratio − 1) <= 0.05` |

`mart_pipeline_vs_exchange` also has a companion summary, `mart_pipeline_vs_exchange_summary`, with one row per symbol: `n_minutes` and `pct_agree`.

**Where the SQL signals honestly differ from Flink:**
- A rolling 60-return window stands in for Flink's EWMA (α = 2/61, which is comparable to a 60-period window).
- `volume > 0` replaces `trade_count ≥ 5`, because exchange candles carry no trade count.
- The model's description says both of these, and `n_flink_matched` shows how much the two actually overlap.

### Tests

- **Generic:**
  - `not_null` on keys;
  - `dbt_utils.unique_combination_of_columns` on every symbol-grain model;
  - `accepted_values` for `source` (pipeline/exchange) and `severity` (LOW/MEDIUM/HIGH);
  - `relationships` from `crypto_id` to `stg_symbols`.
- **Singular** (`tests/`):
  - `assert_ohlc_bounds` (low ≤ open, close ≤ high, volume ≥ 0);
  - `assert_no_future_buckets`;
  - `assert_signals_after_warmup` (every signal has ≥ 30 prior returns).
- **dbt unit tests** (`unit_tests:` YAML):
  - `int_candles_unified`: the pipeline wins when both exist, the exchange fills in when the pipeline is missing, and source is labeled;
  - `int_returns_1m`: a gap minute gives a NULL return;
  - `mart_signals`: a planted spike after 30 flat returns fires; the same spike inside the warm-up does not.
- **Disagreement is a metric, not a test.** A test can't fail because the pipeline and the exchange disagree; that's reported in the mart instead.

### Docs

- Every model and every key column gets a description.
- `dbt docs generate` produces the lineage graph, and `make dbt-docs` serves it.
- `exposures.yml` declares `sub_project_4_analysis`, which depends on the four analysis marts.

## Section 3: Airflow, CI, README

### Airflow (`airflow/`)

- **Setup:**
  - Airflow gets its own venv, `.venv-airflow`, installed by `make airflow-setup` with the official constraints file (`constraints-3.3.2/constraints-3.12.txt`), plus `astronomer-cosmos==1.15.1`.
  - `AIRFLOW_HOME=$(PWD)/airflow`.
  - `.gitignore` ignores `airflow/*` except `airflow/dags/`.
- **Running:** `make airflow` runs `airflow standalone` with the UI on :8080. The generated admin password is in `airflow/simple_auth_manager_passwords.json.generated`, and `make airflow` prints where to find it.
- **DAG `crypto_analytics`** (`airflow/dags/crypto_analytics.py`):
  - `schedule="@hourly"`, `catchup=False`, `max_active_runs=1`, `retries=2`, `retry_delay=5 min`, and a start date a few days back, so the first run is scheduled right away;
  - `backfill_candles`: a `BashOperator` running `cd <repo> && venv/bin/python -m src.backfill candles`;
  - `repair_trade_gaps`: a `BashOperator` running `... -m src.backfill gaps`;
  - `dbt`: a Cosmos `DbtTaskGroup` with `ProjectConfig(analytics/)`, `ProfileConfig(profiles_yml_filepath=analytics/profiles.yml, target_name='dev')`, `ExecutionConfig(dbt_executable_path=<repo>/venv/bin/dbt)` and `RenderConfig(test_behavior=AFTER_EACH)`. Each model gets its own run and test tasks;
  - the order is `backfill_candles >> repair_trade_gaps >> dbt`.
- **Repo path:** the DAG finds the repo root from `__file__`, so there are no hard-coded paths.

### CI (`.github/workflows/ci.yml`)

- **`schema` job:** also runs `configs/migrations/001_analytics.sql` after `init-db.sql`.
- **New `analytics` job:**
  1. a TimescaleDB service container;
  2. apply `init-db.sql` and the migration;
  3. load `tests/sql/analytics_fixture.sql`: 3 hours of synthetic 1-minute candles for BTC and ETH in both candle tables, one planted spike after the warm-up, one planted pipeline/exchange mismatch, and one matching Flink alert;
  4. `pip install -r requirements-analytics.txt`;
  5. `cd analytics && dbt deps && dbt build --target ci`.
- **New `airflow` job:**
  1. Python 3.12;
  2. `pip install "apache-airflow==3.3.2" astronomer-cosmos==1.15.1 --constraint <constraints url>`, with a pip cache;
  3. `pip install -r requirements-analytics.txt`, because Cosmos parses the dbt project at import time;
  4. `AIRFLOW_HOME=$PWD/airflow airflow db migrate && airflow dags list-import-errors`, failing on any output row.
- If the constraints file clashes with dbt in the `airflow` job, the job gets `dbt` from a separate `pip install --target` directory used through `dbt_executable_path`. This is recorded as a ruling if needed.

### Make targets

- `migrate`
- `backfill`
- `dbt`: `cd analytics && ../venv/bin/dbt deps && ../venv/bin/dbt build`
- `dbt-docs`
- `airflow-setup`
- `airflow`

### README

- The Mermaid diagram gains `Coinbase REST → backfill → TimescaleDB → dbt → marts`, with Airflow orchestrating it.
- A short "Analytics" section lists the marts, `make` commands and the docs command.
- New Results rows are filled from the real run:
  - candles modeled;
  - `pct_agree` for pipeline vs exchange;
  - signal precision at 15 min;
  - gaps repaired;
  - Flink-matched signals.

## Out of scope

- Airflow in Docker, cloud deployment, DAG failure alerting.
- The written analysis itself (sub-project 4).
- Replacing the API's hand-written SQL with dbt models.
- True EWMA in SQL.
