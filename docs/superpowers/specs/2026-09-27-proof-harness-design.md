# Sub-project 2: Proof Harness (CI + load + chaos) — Design

**Date:** 2026-09-27
**Status:** Draft for review
**Branch:** `main` (CI already shipped); load and chaos tests go on `feat/proof-harness`

## Context and goal

Sub-project 1 made the pipeline process real Coinbase trades correctly and verified it with one manual acceptance run. The resume still carries claims that were never measured:

- "20+ concurrent users at sub-second p95"
- "sub-millisecond Redis reads"

This sub-project replaces them with numbers that anyone can reproduce with one `make` target, each backed by a committed results file.

**Success means:**

1. CI is green on every push, with a README badge.
2. `make load-test` and `make chaos-test` run against the local stack and write dated JSON results.
3. The README "Results" table shows the headline numbers and links each one to its results file.
4. Every number states its conditions, including the ones that make it look worse.

**Decisions made in chat:**

- **Where tests run:** CI runs only the fast unit and schema checks. Load and chaos tests run locally, and their results are committed (option B).
- **Load tool:** a plain asyncio script using the already-installed `httpx` and `websockets`, not Locust or k6.
- **Chaos scope:** all 5 failure scenarios.

## Part 1: CI — shipped

`.github/workflows/ci.yml` runs 4 parallel jobs on every push and PR to `main`:

| Job | What it does |
|---|---|
| `python` | Python 3.12, pytest (78 tests) |
| `flink` | Temurin Java 11, `mvn -B -q package`, which runs the 22 JUnit tests and builds the JAR |
| `frontend` | Node 20, `npm ci`, `tsc --noEmit`, lint, `next build` |
| `schema` | A `timescale/timescaledb:latest-pg15` service container; loads `configs/init-db.sql`, then runs `tests/sql/schema_checks.sql` with `ON_ERROR_STOP` |

The first run failed because `frontend/package-lock.json` had been resolved on macOS and was missing Linux optional packages (`@emnapi/*`). The lockfile was regenerated under `node:20` on Linux; `npm ci` passes on both Linux and macOS, and the regeneration only added entries. Commit `4bd6337` is green on all 4 jobs.

## Part 2: Load test — `benchmarks/load_test.py`

One asyncio script, run with `make load-test`.

**Preconditions:**
- The full stack is running and the Flink job is deployed.
- The API runs **without `--reload`** as one uvicorn worker. The target starts it that way itself, so reload overhead doesn't distort the numbers.

### Phase 1: REST latency

- **Clients:** 10, then 50, then 100 concurrent `httpx.AsyncClient` workers, 60 s per level.
- **Requests:** each worker loops round-robin over `/api/v1/latest/all`, `/api/v1/latest/BTC`, `/api/v1/historical/BTC?interval=1m` and `/api/v1/trades/BTC?seconds=60`.
- **Recorded per level and per endpoint:**
  - p50, p95 and p99 latency;
  - requests per second;
  - error rate (non-2xx or timeout);
  - the share of `/latest` responses served by Redis (`X-Data-Source`).

### Phase 2: WebSocket fan-out

- **Steps:** 25, 50, 100, 200 and then 400 clients, each connected to `/ws/prices/ALL` for 60 s.
- **Per client:** the count of `trade` frames and the receive time of each.
- **Delivery ratio:** the client's `trade` frame count divided by the highest count any client reached in that step. A client below 0.99 has fallen behind.
- **Fan-out lag:** client receive time (`time.time()`) minus the frame's `time` field, which is the exchange trade time. Reported as p50 and p95.
- **Headline:** the largest step where every client keeps a delivery ratio of at least 0.99. It is reported together with that step's p95 lag.

### Phase 3: Freshness

- **Ingestion lag:** p50 and p95 of `ingest_time − event_time` over `raw_trades` rows in the test window. This is the time from the exchange to the producer.
- **Exchange-to-client lag:** the fan-out lag at the 25-client step.

### Output

- `benchmarks/results/<YYYY-MM-DD>-load.json` stores all raw aggregates plus the run conditions: host OS, CPU count, Docker memory, and uvicorn worker count.
- A summary table is printed to stdout.

### Caveats written into the output and the README

- The load generator and the stack share one laptop, so the numbers are a lower bound on what the API can do.
- The API runs as a single uvicorn worker.
- Exchange-to-client lag includes network delay from Coinbase and the local clock's offset from real time. The script records the NTP offset (`sntp time.apple.com`, or `chronyc tracking` on Linux) when it can, and otherwise marks it as unknown.
- Trade frames go producer → Redis → API and skip Kafka and Flink. That is the live-line path. Candle frames through Flink are covered by the chaos test's consistency check, not by a latency number.

## Part 3: Chaos test — `benchmarks/chaos_test.py`

One script, run with `make chaos-test`. It runs the 5 scenarios in order against the running full stack. Each scenario follows the same steps:

1. **Baseline:** confirm `raw_trades` gained rows in the last 30 s, then wait 60 s.
2. **Fault:** record `t_fault` and apply the fault.
3. **Recover:** poll until recovered, with a 5-minute timeout. Recovery is the first `raw_trades` row with `ingest_time > t_fault`, found after the fault is cleared, for which Flink is also back in `RUNNING` (from the Flink REST API at `:8082`).
4. **Settle:** wait 60 s, then wait until the window's last minute has closed and the watermark has passed it (a +70 s margin).
5. **Check:** run the data checks over `[t_fault − 60 s, t_recovered + 60 s]`.

### Scenarios

| # | Fault | How it's applied | Expected result (measured values are reported even when they differ) |
|---|---|---|---|
| 1 | TaskManager restart | `docker restart flink-taskmanager` | About 15 s recovery from checkpoint, 0 gaps, candles consistent |
| 2 | Kafka broker restart | `docker restart kafka` | Possible gaps (see below) |
| 3 | Postgres down for 30 s | `docker stop postgres`, wait 30 s, `docker start postgres` | The JDBC sinks fail, the job restarts from its checkpoint, 0 gaps, candles consistent |
| 4 | Redis down for 30 s | `docker stop redis`, wait 30 s, `docker start redis` | `/latest/BTC` polled every 200 ms answers 200 throughout with `X-Data-Source: postgres`; 0 gaps. The Flink job keeps running because `RedisSinkFunction` logs and skips write errors, and the producer's `crypto:trades` publish only logs a warning. The script also records how many seconds after `docker start redis` the first WS `trade` frame arrives, which tests the API pub/sub reconnect |
| 5 | Producer restart | Kill the producer process and restart it the same way `start_pipeline.sh` does | A counted gap for every trade that happened while it was down |

**Scenario 2 is expected to lose data.** The producer uses `retries=5` with kafka-python's default 100 ms backoff. That retry budget is shorter than a broker restart, so trades sent during the outage may fail. The expected result is "gaps equal to the producer's `send_errors`", which is a known ceiling recorded under Known limitations, not a pass. A fix, for example a bounded local buffer with replay or a longer retry budget, is out of scope for this sub-project. The measured gap motivates it.

**Producer control (scenario 5):** the script kills only the PID it finds with `pgrep -f src.producers.coinbase_trades_producer`, the same pattern `stop_pipeline.sh` uses. It restarts the producer with the same command and log redirect as `start_pipeline.sh`. It never kills anything broader.

**Container names** come from `docker-compose.yml`: `flink-taskmanager`, `kafka`, `postgres`, `redis`.

### Data checks (SQL, in `benchmarks/checks.sql` and loaded by the script)

- **Gaps (lost trades):** for each `crypto_id`, compare each row with the previous one, ordered by `trade_id`, within the window. Sum `trade_id − prev_trade_id − 1` wherever it's greater than 0, and report the sum per symbol. Coinbase `trade_id` goes up by exactly 1 per product (verified in sub-project 1), so any gap is a lost trade.
- **Candle consistency (double counting):** for every closed minute in the window, `price_aggregates_1m.trade_count` must equal `count(*)` of `raw_trades` rows in `[window_start, window_end)` for that symbol. Minutes that only partly overlap the window's edges are excluded. The number of mismatched minutes is reported.
- **Duplicates:** not checked directly. The `raw_trades` primary key `(crypto_id, trade_id, event_time)` rejects exact duplicates, and Flink's dedup plus the candle-consistency check cover the ones that matter.

### Output

- `benchmarks/results/<YYYY-MM-DD>-chaos.json` holds, for each scenario:
  - `t_fault`, `t_recovered` and `recovery_seconds`;
  - gaps per symbol and in total;
  - mismatched candle minutes;
  - the producer's `send_errors` from its last stats log line;
  - for scenario 4 only, API availability (share of 200s) and the share of responses by data source.
- A summary table is printed.
- A scenario that hits the 5-minute timeout is recorded as `recovered: false`, and the run continues with the next scenario after trying to restore the service.

### Safety

- The script checks at startup that it is pointed at the local compose stack (the `postgres` container exists and is on host port 5433), and refuses to run otherwise.
- No volume is ever deleted. Faults only use `restart`, `stop` and `start`.
- If the script is interrupted (Ctrl-C), it restarts any container it stopped before exiting.

## Testing the harness

A broken check query would make every scenario look clean, so the SQL gets its own test:

- **`tests/sql/chaos_checks_test.sql`:**
  1. Seeds `raw_trades` with trade_ids 1–10, 13–20 (a gap of 2) and one candle whose `trade_count` is off by one.
  2. Runs `benchmarks/checks.sql`.
  3. Raises an exception unless it reports exactly 2 gaps and 1 mismatched minute.
- **CI:** the test runs in the existing `schema` job, as one more `psql -v ON_ERROR_STOP=1` step.
- **Python helpers:** the pure functions in the load test (percentile calculation and delivery ratio) get a small pytest file, `tests/benchmarks/test_stats.py`.

## Make targets

- `make load-test` starts the API without reload on :8000 (or fails if :8000 is already in use by a reload server), runs `benchmarks/load_test.py`, then stops the API it started.
- `make chaos-test` runs `benchmarks/chaos_test.py`.

## README changes

- The "Results" table gets rows for:
  - REST p95 at 50 clients;
  - concurrent WebSocket clients at ≥ 99% delivery, with their p95 lag;
  - p95 ingestion lag;
  - recovery time and gaps per chaos scenario.
- Each row links to its JSON file in `benchmarks/results/`.
- "Known limitations" gets the scenario 2 finding and the same-laptop caveat.

## Out of scope

- Running load or chaos tests in CI.
- Fixing the Kafka-restart data loss, or adding producer backfill. Both are candidates for sub-project 3, which already includes a Coinbase REST backfill.
- Multi-worker API benchmarks, and load generation from a separate machine.
- Grafana/Prometheus dashboards.

## Resume impact

The two unmeasured claims are replaced with measured ones, for example "serves N concurrent WebSocket clients at p95 X ms" or "recovers from broker, database and TaskManager failures in Y s with 0 lost trades", where the data supports that. Where it doesn't, the result is an honest documented limit, which interviewers tend to find more convincing than a perfect number.
