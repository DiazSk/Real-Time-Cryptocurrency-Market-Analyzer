# Proof Harness (load + chaos) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two reproducible benchmark scripts, `make load-test` and `make chaos-test`, that write committed JSON results. The results replace unmeasured resume claims with measured numbers.

**Architecture:** A `benchmarks/` directory holds:
- pure metric helpers (`stats.py`, unit-tested);
- shared plumbing (`common.py`: short-lived DB queries, the API launcher, the results writer);
- two asyncio scripts, run as modules;
- `checks.sql`, which defines two SQL functions used by the chaos test to find lost trades and inconsistent candles. The functions are tested in CI by a seeded SQL test.

**Tech Stack:** Python 3.12, asyncio, `httpx`, `websockets` 13.1 (`websockets.asyncio.client`), `asyncpg`, and the Docker CLI. All dependencies are already installed. PostgreSQL/TimescaleDB with plpgsql.

**Spec:** `docs/superpowers/specs/2026-09-27-proof-harness-design.md` (Part 1, CI, is already shipped).

## Global Constraints

- No new Python or npm dependencies.
- Commits carry **no** `Co-Authored-By`/"Generated with" lines. See `CLAUDE.md`.
- Run the scripts as modules (`python -m benchmarks.load_test`) so `from src.config import ...` and `from benchmarks.stats import ...` resolve from the repo root.
- Chaos faults only use `docker restart|stop|start` and the producer's own PID (`pgrep -f src.producers.coinbase_trades_producer`). Never delete volumes, and never use a broad `pkill`.
- Chaos refuses to run unless `docker port postgres 5432` maps to host port `5433`, which marks the local compose stack.
- Load test: 10/50/100 REST clients at 60 s each; 25/50/100/200/400 WS clients at 60 s each; delivery threshold `0.99`.
- Chaos: 60 s baseline; 30 s outage for postgres and redis; 5-minute recovery timeout; 60 s settle plus a 70 s watermark margin; check window `[t_fault − 60 s, t_recovered + 60 s]`.
- Results go to `benchmarks/results/<YYYY-MM-DD>-load.json` and `-chaos.json`. `.gitignore` ignores `*.json`, so these need an explicit exception.
- The load test runs the API **without `--reload`** as one uvicorn process. It refuses to start if `:8000` is already in use.

## Review Focus

1. **No trades during a WS step** (quiet market, or the producer is down). This must count as a *failed* step, not a vacuous pass. Pinned in Task 1 (`step_passed([0, 0])` is False).
2. **Every request in a level errored.** The percentiles must come back as `None` rather than crashing the run. Pinned in Task 1 (`percentiles([])`).
3. **One noisy step passes after a failed one** (e.g. 50 fails, 100 passes). The headline must stop at the first failure (25), not report 100. Pinned in Task 1.
4. **Trades outside the check window**, and the first trade inside it (which has no previous trade). Neither may create a phantom gap. Pinned in Task 2's SQL test (trade 30, outside the window, adds no gap).
5. **Ctrl-C mid-outage** must restart the stopped container and the killed producer. Pinned in Task 4, Step 3, with a manual interrupt check.

Also watched, but not pinned by a test: a trade later than Flink's 2 s watermark is stored in `raw_trades` but left out of its candle. `chaos_candle_mismatches` returns the symbol, minute and both counts, so a mismatch can be diagnosed, and the README must report any mismatch honestly rather than hide it.

---

### Task 1: Metric helpers

**Files:**
- Create: `benchmarks/stats.py`
- Test: `tests/benchmarks/test_stats.py`

**Interfaces:**
- Produces (all pure):
  - `percentiles(values: list[float]) -> dict` with keys `p50`, `p95`, `p99` (each a float, or None);
  - `delivery_ratios(counts: list[int]) -> list[float]`;
  - `step_passed(counts: list[int], threshold: float = 0.99) -> bool`;
  - `max_passing_step(steps: list[dict]) -> int | None`, where each step dict has `clients: int` and `passed: bool`;
  - `parse_send_errors(log_text: str) -> int | None`;
  - `send_errors_delta(before: int | None, after: int | None) -> int | None`.

- [ ] **Step 1: Write the failing tests**

```python
from benchmarks.stats import (
    delivery_ratios,
    max_passing_step,
    parse_send_errors,
    percentiles,
    send_errors_delta,
    step_passed,
)


def test_percentiles_interpolate_between_samples():
    p = percentiles(list(range(1, 101)))
    assert p["p50"] == 50.5
    assert round(p["p95"], 2) == 95.05
    assert round(p["p99"], 2) == 99.01


def test_percentiles_of_empty_and_single():
    assert percentiles([]) == {"p50": None, "p95": None, "p99": None}
    assert percentiles([7]) == {"p50": 7.0, "p95": 7.0, "p99": 7.0}


def test_delivery_ratio_is_relative_to_the_best_client():
    assert delivery_ratios([100, 99, 50]) == [1.0, 0.99, 0.5]
    assert delivery_ratios([0, 0]) == [0.0, 0.0]


def test_step_passes_only_when_every_client_keeps_up_and_trades_flowed():
    assert step_passed([100, 99])
    assert not step_passed([100, 98])
    assert not step_passed([0, 0])  # no trades at all is not a pass
    assert not step_passed([])


def test_headline_stops_at_the_first_failed_step():
    steps = [
        {"clients": 25, "passed": True},
        {"clients": 50, "passed": False},
        {"clients": 100, "passed": True},
    ]
    assert max_passing_step(steps) == 25
    assert max_passing_step([{"clients": 25, "passed": False}]) is None


def test_parse_send_errors_takes_the_last_stats_line():
    log = (
        "2026-09-27 01:00:00,000 stats {'published': 5, 'invalid': 0, 'duplicates': 0, "
        "'send_errors': 1, 'reconnects': 0} missed_trades=0\n"
        "2026-09-27 01:01:00,000 stats {'published': 9, 'invalid': 0, 'duplicates': 0, "
        "'send_errors': 4, 'reconnects': 0} missed_trades=2\n"
    )
    assert parse_send_errors(log) == 4
    assert parse_send_errors("no stats yet") is None


def test_send_errors_delta_handles_a_restarted_producer():
    assert send_errors_delta(3, 7) == 4
    assert send_errors_delta(7, 2) == 2  # counter reset by a restart
    assert send_errors_delta(None, 2) is None
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `venv/bin/python -m pytest tests/benchmarks/test_stats.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'benchmarks'`

- [ ] **Step 3: Implement**

```python
"""Pure metric helpers for the benchmark scripts (tested in tests/benchmarks/test_stats.py)."""

import re
import statistics

_SEND_ERRORS = re.compile(r"'send_errors': (\d+)")


def percentiles(values):
    """p50/p95/p99 with linear interpolation; None for each when there are no samples."""
    if not values:
        return {"p50": None, "p95": None, "p99": None}
    if len(values) == 1:
        v = float(values[0])
        return {"p50": v, "p95": v, "p99": v}
    q = statistics.quantiles(values, n=100, method="inclusive")
    return {"p50": q[49], "p95": q[94], "p99": q[98]}


def delivery_ratios(counts):
    """Each client's frame count relative to the best client in the same step."""
    top = max(counts, default=0)
    return [c / top if top else 0.0 for c in counts]


def step_passed(counts, threshold=0.99):
    """A step passes only if trades flowed and every client got at least `threshold` of them."""
    ratios = delivery_ratios(counts)
    return bool(ratios) and max(counts) > 0 and min(ratios) >= threshold


def max_passing_step(steps):
    """Largest client count before the first failed step (steps in ascending order)."""
    best = None
    for step in sorted(steps, key=lambda s: s["clients"]):
        if not step["passed"]:
            break
        best = step["clients"]
    return best


def parse_send_errors(log_text):
    """send_errors from the producer's most recent `stats {...}` log line."""
    found = _SEND_ERRORS.findall(log_text)
    return int(found[-1]) if found else None


def send_errors_delta(before, after):
    """Errors during a scenario; a smaller `after` means the producer restarted and the counter reset."""
    if before is None or after is None:
        return None
    return after - before if after >= before else after
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `venv/bin/python -m pytest tests/benchmarks/test_stats.py -q`, then `venv/bin/python -m pytest -q`
Expected: 7 passed, then 85 passed overall.

- [ ] **Step 5: Commit**

```bash
git add benchmarks/stats.py tests/benchmarks/test_stats.py
git commit -m "feat(benchmarks): percentile, delivery-ratio and producer-log helpers"
```

---

### Task 2: Chaos data checks in SQL, tested in CI

**Files:**
- Create: `benchmarks/checks.sql`
- Create: `tests/sql/chaos_checks_test.sql`
- Modify: `.github/workflows/ci.yml` (the `schema` job: one more step)

**Interfaces:**
- Produces:
  - `chaos_gaps(t0 timestamptz, t1 timestamptz) RETURNS TABLE (symbol text, gaps bigint)`: one row per symbol that has trades in `[t0, t1)`;
  - `chaos_candle_mismatches(t0 timestamptz, t1 timestamptz) RETURNS TABLE (symbol text, minute timestamptz, candle_count bigint, raw_count bigint)`: one row per full minute inside the window where the counts differ, or where only one side exists.

- [ ] **Step 1: Write the failing SQL test** (`tests/sql/chaos_checks_test.sql`)

```sql
-- Run after configs/init-db.sql (the CI schema job runs it after schema_checks.sql).
-- Seeds ETH with a known gap and one bad candle, then asserts benchmarks/checks.sql reports exactly that.
\i benchmarks/checks.sql

CREATE TEMP TABLE cc AS SELECT date_trunc('hour', now()) - INTERVAL '5 hours' AS base;

-- trade_ids 1-10 and 13-20 (gap of 2) inside minute base+1m; 21 inside minute base+2m.
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT c.id, g, 100, 1, 'buy', g, (SELECT base FROM cc) + INTERVAL '1 minute' + g * INTERVAL '1 second', now()
FROM cryptocurrencies c, generate_series(1, 20) g
WHERE c.symbol = 'ETH' AND g NOT IN (11, 12);
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT c.id, 21, 100, 1, 'buy', 21, (SELECT base FROM cc) + INTERVAL '2 minutes 5 seconds', now()
FROM cryptocurrencies c WHERE c.symbol = 'ETH';
-- trade 30 is outside the window: it must not add a gap of 8.
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time)
SELECT c.id, 30, 100, 1, 'buy', 30, (SELECT base FROM cc) + INTERVAL '20 minutes', now()
FROM cryptocurrencies c WHERE c.symbol = 'ETH';

-- Minute base+1m has 18 trades but the candle says 17 (a mismatch); base+2m is correct.
INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, low_price,
                                 close_price, vwap, volume, quote_volume, trade_count)
SELECT c.id, b, b + INTERVAL '1 minute', 100, 100, 100, 100, 100, 17, 1700, 17
FROM cryptocurrencies c, (SELECT base + INTERVAL '1 minute' AS b FROM cc) t WHERE c.symbol = 'ETH';
INSERT INTO price_aggregates_1m (crypto_id, window_start, window_end, open_price, high_price, low_price,
                                 close_price, vwap, volume, quote_volume, trade_count)
SELECT c.id, b, b + INTERVAL '1 minute', 100, 100, 100, 100, 100, 1, 100, 1
FROM cryptocurrencies c, (SELECT base + INTERVAL '2 minutes' AS b FROM cc) t WHERE c.symbol = 'ETH';

DO $$
DECLARE
  t0 timestamptz := (SELECT base FROM cc);
  t1 timestamptz := (SELECT base FROM cc) + INTERVAL '10 minutes';
  g bigint;
  m bigint;
BEGIN
  SELECT gaps INTO g FROM chaos_gaps(t0, t1) WHERE symbol = 'ETH';
  IF g IS DISTINCT FROM 2 THEN RAISE EXCEPTION 'chaos_gaps: expected 2 for ETH, got %', g; END IF;
  SELECT count(*) INTO m FROM chaos_candle_mismatches(t0, t1);
  IF m <> 1 THEN RAISE EXCEPTION 'chaos_candle_mismatches: expected 1 row, got %', m; END IF;
END $$;

\echo 'chaos_checks: ALL PASSED'
```

- [ ] **Step 2: Run it against a throwaway TimescaleDB and confirm it fails**

```bash
docker run -d --rm --name chaos-sql-check -e POSTGRES_USER=crypto_user -e POSTGRES_PASSWORD=ci -e POSTGRES_DB=crypto_db timescale/timescaledb:latest-pg15
until docker exec chaos-sql-check pg_isready -U crypto_user -d crypto_db -h localhost >/dev/null 2>&1; do sleep 2; done; sleep 2
docker cp configs/init-db.sql chaos-sql-check:/init.sql && docker exec chaos-sql-check mkdir -p /w/benchmarks /w/tests/sql
docker exec chaos-sql-check psql -U crypto_user -d crypto_db -v ON_ERROR_STOP=1 -q -f /init.sql >/dev/null
docker cp tests/sql/chaos_checks_test.sql chaos-sql-check:/w/tests/sql/
docker exec -w /w chaos-sql-check psql -U crypto_user -d crypto_db -v ON_ERROR_STOP=1 -q -f tests/sql/chaos_checks_test.sql
```
Expected: FAIL, because `benchmarks/checks.sql: No such file or directory`.

- [ ] **Step 3: Implement** (`benchmarks/checks.sql`)

```sql
-- Chaos-test data checks. Loaded by benchmarks/chaos_test.py and tests/sql/chaos_checks_test.sql.
-- Coinbase trade_id rises by exactly 1 per product, so a jump inside the window is a lost trade.

CREATE OR REPLACE FUNCTION chaos_gaps(t0 timestamptz, t1 timestamptz)
RETURNS TABLE (symbol text, gaps bigint) LANGUAGE sql STABLE AS $$
  SELECT c.symbol::text, COALESCE(sum(d.gap) FILTER (WHERE d.gap > 0), 0)::bigint
  FROM (
    SELECT rt.crypto_id,
           rt.trade_id - lag(rt.trade_id) OVER (PARTITION BY rt.crypto_id ORDER BY rt.trade_id) - 1 AS gap
    FROM raw_trades rt
    WHERE rt.event_time >= t0 AND rt.event_time < t1
  ) d
  JOIN cryptocurrencies c ON c.id = d.crypto_id
  GROUP BY c.symbol
  ORDER BY c.symbol
$$;

-- Full minutes inside the window where the candle's trade_count disagrees with raw_trades
-- (or only one side exists). Catches double counting after a Flink recovery.
CREATE OR REPLACE FUNCTION chaos_candle_mismatches(t0 timestamptz, t1 timestamptz)
RETURNS TABLE (symbol text, minute timestamptz, candle_count bigint, raw_count bigint)
LANGUAGE sql STABLE AS $$
  WITH bounds AS (
    SELECT date_trunc('minute', t0) + INTERVAL '1 minute' AS lo, date_trunc('minute', t1) AS hi
  ), r AS (
    SELECT rt.crypto_id, date_trunc('minute', rt.event_time) AS m, count(*) AS n
    FROM raw_trades rt, bounds
    WHERE rt.event_time >= bounds.lo AND rt.event_time < bounds.hi
    GROUP BY 1, 2
  ), p AS (
    SELECT pa.crypto_id, pa.window_start AS m, pa.trade_count::bigint AS n
    FROM price_aggregates_1m pa, bounds
    WHERE pa.window_start >= bounds.lo AND pa.window_end <= bounds.hi
  )
  SELECT c.symbol::text, COALESCE(p.m, r.m), p.n, r.n
  FROM p FULL JOIN r ON p.crypto_id = r.crypto_id AND p.m = r.m
  JOIN cryptocurrencies c ON c.id = COALESCE(p.crypto_id, r.crypto_id)
  WHERE p.n IS DISTINCT FROM r.n
  ORDER BY 1, 2
$$;
```

- [ ] **Step 4: Run the test again and confirm it passes, then clean up**

```bash
docker cp benchmarks/checks.sql chaos-sql-check:/w/benchmarks/
docker exec -w /w chaos-sql-check psql -U crypto_user -d crypto_db -v ON_ERROR_STOP=1 -q -f tests/sql/chaos_checks_test.sql
docker stop chaos-sql-check
```
Expected: `chaos_checks: ALL PASSED`

- [ ] **Step 5: Add the CI step.** In `.github/workflows/ci.yml`, `schema` job, after the `schema_checks.sql` step, add:

```yaml
      - run: psql -v ON_ERROR_STOP=1 -q -f tests/sql/chaos_checks_test.sql
```

- [ ] **Step 6: Commit**

```bash
git add benchmarks/checks.sql tests/sql/chaos_checks_test.sql .github/workflows/ci.yml
git commit -m "feat(benchmarks): SQL gap and candle-consistency checks, tested in CI"
```

---

### Task 3: Shared plumbing and the load test

**Files:**
- Create: `benchmarks/common.py`
- Create: `benchmarks/load_test.py`
- Modify: `Makefile` (add `load-test` and `chaos-test` to `.PHONY` and add both targets; `chaos-test` is used by Task 4)
- Modify: `.gitignore` (add `!benchmarks/results/*.json` after the `!frontend/components.json` line)

**Interfaces:**
- Consumes: Task 1's `percentiles`, `step_passed`, `delivery_ratios` and `max_passing_step`.
- `benchmarks/common.py` produces:
  - `API_URL = "http://localhost:8000"` and `WS_URL = "ws://localhost:8000"`;
  - `async query(sql: str, *args) -> list[asyncpg.Record]`;
  - `raise_fd_limit() -> None`;
  - `api_server(reuse: bool)`, a context manager;
  - `write_results(kind: str, payload: dict) -> Path`;
  - `run_conditions() -> dict`;
  - `utcnow() -> datetime`.

- [ ] **Step 1: Write `benchmarks/common.py`**

```python
"""Shared plumbing for the benchmark scripts: DB access, API launch, results files."""

import json
import os
import platform
import resource
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx

from src.config import POSTGRES_CONNECT_KWARGS

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "benchmarks" / "results"


def utcnow():
    return datetime.now(timezone.utc)


async def query(sql, *args):
    """One short-lived connection per call, so a Postgres restart can't strand the script."""
    conn = await asyncpg.connect(**POSTGRES_CONNECT_KWARGS, timeout=5)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def raise_fd_limit():
    """400 WebSocket clients need more than macOS's default 256 open files (inherited by the API we launch)."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = 4096 if hard == resource.RLIM_INFINITY else min(4096, hard)
    if soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))


def _port_in_use(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


@contextmanager
def api_server(reuse):
    """Yield with a healthy API on :8000.

    reuse=True accepts an API that is already running (chaos test).
    reuse=False insists on launching a fresh single-process API without --reload (load test).
    """
    if _port_in_use(8000):
        if reuse:
            yield
            return
        sys.exit("Port 8000 is in use (probably `make api`, which runs with --reload). Stop it and rerun.")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", "8000", "--log-level", "warning"],
        cwd=ROOT,
    )
    try:
        for _ in range(60):
            if proc.poll() is not None:
                sys.exit("The API exited during startup; run `make api` to see why.")
            try:
                if httpx.get(f"{API_URL}/health", timeout=1).is_success:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            sys.exit("The API did not become healthy within 30 s.")
        yield
    finally:
        proc.terminate()
        proc.wait(10)


def run_conditions():
    """Where the numbers came from; stored in every results file."""
    docker_mem = subprocess.run(
        ["docker", "info", "--format", "{{.MemTotal}}"], capture_output=True, text=True
    ).stdout.strip()
    return {
        "host": platform.platform(),
        "cpu_count": os.cpu_count(),
        "docker_mem_bytes": int(docker_mem) if docker_mem.isdigit() else None,
        "api_workers": 1,
        "load_generator": "same machine as the stack",
    }


def write_results(kind, payload):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{utcnow():%Y-%m-%d}-{kind}.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return path
```

- [ ] **Step 2: Write `benchmarks/load_test.py`**

```python
"""Load test: REST latency, WebSocket fan-out, and freshness against the local stack.

Run with `make load-test` (full stack up, Flink job deployed, nothing on :8000).
"""

import argparse
import asyncio
import json
import subprocess
import time
from collections import Counter, defaultdict

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from benchmarks.common import API_URL, WS_URL, api_server, query, raise_fd_limit, run_conditions, utcnow, write_results
from benchmarks.stats import delivery_ratios, max_passing_step, percentiles, step_passed

ENDPOINTS = [
    "/api/v1/latest/all",
    "/api/v1/latest/BTC",
    "/api/v1/historical/BTC?interval=1m",
    "/api/v1/trades/BTC?seconds=60",
]


async def _rest_worker(client, deadline, samples, errors, sources):
    i = 0
    while time.monotonic() < deadline:
        path = ENDPOINTS[i % len(ENDPOINTS)]
        i += 1
        start = time.perf_counter()
        try:
            r = await client.get(path)
        except httpx.HTTPError:
            errors[path] += 1
            continue
        if r.is_success:
            samples[path].append((time.perf_counter() - start) * 1000)
            if path.startswith("/api/v1/latest"):
                sources[r.headers.get("x-data-source", "none")] += 1
        else:
            errors[path] += 1


async def rest_level(clients, seconds):
    samples, errors, sources = defaultdict(list), Counter(), Counter()
    limits = httpx.Limits(max_connections=clients, max_keepalive_connections=clients)
    async with httpx.AsyncClient(base_url=API_URL, timeout=5, limits=limits) as client:
        deadline = time.monotonic() + seconds
        await asyncio.gather(*(_rest_worker(client, deadline, samples, errors, sources) for _ in range(clients)))
    endpoints = {}
    for path in ENDPOINTS:
        ok = samples[path]
        total = len(ok) + errors[path]
        endpoints[path] = {
            "requests": total,
            "rps": total / seconds,
            "error_rate": errors[path] / total if total else None,
            "latency_ms": percentiles(ok),
        }
    all_ok = [ms for path in ENDPOINTS for ms in samples[path]]
    return {"clients": clients, "latency_ms": percentiles(all_ok), "endpoints": endpoints, "latest_sources": dict(sources)}


async def _read_trades(ws, deadline, lags_ms):
    count = 0
    while (left := deadline - time.monotonic()) > 0:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=left)
        except (asyncio.TimeoutError, ConnectionClosed):
            break
        msg = json.loads(raw)
        if msg.get("type") == "trade" and msg.get("time") is not None:
            count += 1
            lags_ms.append((time.time() - float(msg["time"])) * 1000)
    return count


async def ws_step(clients, seconds):
    conns = await asyncio.gather(
        *(connect(f"{WS_URL}/ws/prices/ALL", open_timeout=30) for _ in range(clients)), return_exceptions=True
    )
    ok = [c for c in conns if not isinstance(c, BaseException)]
    lags_ms = []
    deadline = time.monotonic() + seconds  # measure only once everyone is connected
    counts = list(await asyncio.gather(*(_read_trades(c, deadline, lags_ms) for c in ok)))
    await asyncio.gather(*(c.close() for c in ok), return_exceptions=True)
    counts += [0] * (clients - len(ok))  # a client that never connected received nothing
    ratios = delivery_ratios(counts)
    return {
        "clients": clients,
        "connected": len(ok),
        "max_trades": max(counts, default=0),
        "min_delivery_ratio": min(ratios, default=0.0),
        "passed": step_passed(counts),
        "lag_ms": percentiles(lags_ms),
    }


async def ingestion_lag(since):
    rows = await query(
        """SELECT percentile_cont(ARRAY[0.5, 0.95]) WITHIN GROUP
                  (ORDER BY extract(epoch FROM ingest_time - event_time) * 1000) AS p
           FROM raw_trades WHERE ingest_time >= $1""",
        since,
    )
    p = rows[0]["p"]
    return {"p50": p[0], "p95": p[1]} if p else {"p50": None, "p95": None}


def clock_offset_seconds():
    """Local clock minus NTP time via macOS sntp, or None when it can't be measured."""
    try:
        out = subprocess.run(["sntp", "time.apple.com"], capture_output=True, text=True, timeout=10).stdout
        return float(out.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


async def run(args):
    started = utcnow()
    rest = []
    for level in args.levels:
        print(f"REST: {level} clients for {args.rest_seconds}s")
        rest.append(await rest_level(level, args.rest_seconds))
    ws = []
    for step in args.ws_steps:
        print(f"WS: {step} clients for {args.ws_seconds}s")
        ws.append(await ws_step(step, args.ws_seconds))
    return {
        "started": started,
        "conditions": run_conditions() | {"clock_offset_seconds": clock_offset_seconds()},
        "rest": rest,
        "websocket": {"steps": ws, "max_clients_at_99pct_delivery": max_passing_step(ws)},
        "freshness": {
            "ingestion_lag_ms": await ingestion_lag(started),
            "exchange_to_client_lag_ms": ws[0]["lag_ms"] if ws else None,
        },
        "caveats": [
            "Load generator and stack share one machine; numbers are a lower bound.",
            "API runs as a single uvicorn process.",
            "Exchange-to-client lag includes Coinbase network delay and local clock offset.",
            "Trade frames take producer -> Redis -> API and skip Kafka/Flink.",
        ],
    }


def _fmt(v):
    return "-" if v is None else f"{v:.1f}"


def summarize(result):
    print("\nREST (all endpoints)      p50     p95     p99   ms")
    for level in result["rest"]:
        lat = level["latency_ms"]
        print(f"  {level['clients']:>3} clients         {_fmt(lat['p50']):>7} {_fmt(lat['p95']):>7} {_fmt(lat['p99']):>7}")
    print("\nWebSocket  clients  connected  min delivery  p95 lag ms  passed")
    for s in result["websocket"]["steps"]:
        print(f"           {s['clients']:>7}  {s['connected']:>9}  {s['min_delivery_ratio']:>12.3f}  "
              f"{_fmt(s['lag_ms']['p95']):>10}  {s['passed']}")
    print(f"\nMax clients at >=99% delivery: {result['websocket']['max_clients_at_99pct_delivery']}")
    lag = result["freshness"]["ingestion_lag_ms"]
    print(f"Ingestion lag p50/p95 ms: {_fmt(lag['p50'])} / {_fmt(lag['p95'])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rest-seconds", type=int, default=60)
    parser.add_argument("--ws-seconds", type=int, default=60)
    parser.add_argument("--levels", type=lambda s: [int(x) for x in s.split(",")], default=[10, 50, 100])
    parser.add_argument("--ws-steps", type=lambda s: [int(x) for x in s.split(",")], default=[25, 50, 100, 200, 400])
    parser.add_argument("--no-save", action="store_true", help="smoke runs: print only, don't write results")
    args = parser.parse_args()
    raise_fd_limit()
    with api_server(reuse=False):
        result = asyncio.run(run(args))
    summarize(result)
    if not args.no_save:
        print(f"\nWrote {write_results('load', result)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Add the Make targets and the `.gitignore` exception**

In `Makefile`, append `load-test chaos-test` to the `.PHONY` line. After the `test:` target, add:

```make
load-test: ## Benchmark REST latency, WebSocket fan-out and freshness (full stack up; nothing on :8000)
	$(PYTHON_CMD) -m benchmarks.load_test

chaos-test: ## Inject 5 failures and measure recovery, lost trades and candle consistency (full stack up)
	$(PYTHON_CMD) -m benchmarks.chaos_test
```

In `.gitignore`, add after `!frontend/components.json`:

```
!benchmarks/results/*.json
```

- [ ] **Step 4: Smoke-run against the live stack**

Preconditions: `docker compose up -d`, `bash scripts/start_pipeline.sh`, `make build-flink deploy-flink`, and nothing listening on :8000.

Run: `venv/bin/python -m benchmarks.load_test --rest-seconds 5 --ws-seconds 10 --levels 10 --ws-steps 25 --no-save`
Expected:
- the summary tables print;
- 10-client p95 is a number, not `-`;
- the 25-client step shows `connected 25`, `passed True` and `max_trades > 0`;
- the ingestion lag values are numbers;
- the launched API is gone afterwards (`lsof -ti :8000` prints nothing).

Then check the port guard: start `make api` in another terminal, rerun the command, and expect it to exit with "Port 8000 is in use". Stop `make api` afterwards.

- [ ] **Step 5: Run the unit tests, then commit**

Run: `venv/bin/python -m pytest -q` (expect 85 passed)

```bash
git add benchmarks/common.py benchmarks/load_test.py Makefile .gitignore
git commit -m "feat(benchmarks): load test for REST latency, WebSocket fan-out and freshness"
```

---

### Task 4: Chaos test

**Files:**
- Create: `benchmarks/chaos_test.py`

**Interfaces:**
- Consumes:
  - from Task 1: `parse_send_errors` and `send_errors_delta`;
  - from Task 2: `chaos_gaps(t0, t1)` and `chaos_candle_mismatches(t0, t1)`, via `benchmarks/checks.sql`;
  - from Task 3: `API_URL`, `WS_URL`, `ROOT`, `api_server`, `query`, `utcnow`, `write_results` and `run_conditions`.
- Produces: `benchmarks/results/<date>-chaos.json` with a `scenarios` list. Each item has these keys:
  - `name`, `t_fault`, `t_cleared`, `t_recovered`, `recovered`;
  - `recovery_seconds`, `outage_seconds`;
  - `gaps_by_symbol`, `gaps_total`;
  - `candle_mismatches`, `send_errors_delta`, `flink_running`;
  - for `redis` only: `api_probe` and `ws_trade_resumed_seconds`.

- [ ] **Step 1: Write `benchmarks/chaos_test.py`**

```python
"""Chaos test: inject 5 failures and measure recovery time, lost trades and candle consistency.

Run with `make chaos-test` against the full local stack (Flink job deployed, producer running).
"""

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import timedelta

import asyncpg
import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from benchmarks.common import API_URL, ROOT, WS_URL, api_server, query, run_conditions, utcnow, write_results
from benchmarks.stats import parse_send_errors, send_errors_delta
from src.config import POSTGRES_CONNECT_KWARGS

SCENARIOS = ["taskmanager", "kafka", "postgres", "redis", "producer"]
PRODUCER = "src.producers.coinbase_trades_producer"
PRODUCER_LOG = ROOT / "logs" / "producer.log"
BASELINE_S, OUTAGE_S, RECOVERY_TIMEOUT_S, SETTLE_S = 60, 30, 300, 60 + 70
CHECKS_SQL = (ROOT / "benchmarks" / "checks.sql").read_text()

stopped_containers = set()  # restarted on exit, even after Ctrl-C
producer_killed = False


def docker(*args):
    subprocess.run(["docker", *args], check=True, capture_output=True, text=True)


def assert_local_stack():
    out = subprocess.run(["docker", "port", "postgres", "5432"], capture_output=True, text=True).stdout
    if ":5433" not in out:
        sys.exit("Refusing to run: the `postgres` container is not the local compose stack on host port 5433.")


def send_errors_now():
    return parse_send_errors(PRODUCER_LOG.read_text(errors="replace")) if PRODUCER_LOG.exists() else None


def producer_pids():
    out = subprocess.run(["pgrep", "-f", PRODUCER], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if int(p) != os.getpid()]


def start_producer():
    PRODUCER_LOG.parent.mkdir(exist_ok=True)
    log = open(PRODUCER_LOG, "a")
    subprocess.Popen([sys.executable, "-m", PRODUCER], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                     start_new_session=True)  # outlives this script, like start_pipeline.sh


def restart_producer():
    global producer_killed
    pids = producer_pids()
    if not pids:
        raise RuntimeError("producer is not running; start it with scripts/start_pipeline.sh")
    for pid in pids:
        os.kill(pid, signal.SIGTERM)
    producer_killed = True
    for _ in range(20):
        if not producer_pids():
            break
        time.sleep(0.5)
    else:
        for pid in producer_pids():
            os.kill(pid, signal.SIGKILL)
    start_producer()
    producer_killed = False


def flink_running():
    try:
        jobs = httpx.get("http://localhost:8082/jobs/overview", timeout=3).json()["jobs"]
        return any(j["state"] == "RUNNING" for j in jobs)
    except (httpx.HTTPError, KeyError, ValueError):
        return False


async def rows_since(ts):
    try:
        rows = await query("SELECT EXISTS (SELECT 1 FROM raw_trades WHERE ingest_time > $1) AS e", ts)
        return rows[0]["e"]
    except (OSError, asyncpg.PostgresError, asyncio.TimeoutError):
        return False  # Postgres is down or restarting


async def wait_recovered(t_cleared):
    """First moment a trade ingested after the fault was cleared is in raw_trades (the whole path works)."""
    deadline = time.monotonic() + RECOVERY_TIMEOUT_S
    while time.monotonic() < deadline:
        if await rows_since(t_cleared):
            return utcnow()
        await asyncio.sleep(1)
    return None


async def probe_latest(stop):
    ok = total = 0
    sources = Counter()
    async with httpx.AsyncClient(base_url=API_URL, timeout=2) as client:
        while not stop.is_set():
            total += 1
            try:
                r = await client.get("/api/v1/latest/BTC")
                if r.status_code == 200:
                    ok += 1
                    sources[r.headers.get("x-data-source", "none")] += 1
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
    return {"requests": total, "availability": ok / total if total else None, "sources": dict(sources)}


async def first_trade_after(cleared, cleared_at):
    """Seconds from `docker start redis` to the first WS trade frame for a trade made after it."""
    async with connect(f"{WS_URL}/ws/prices/ALL", open_timeout=30) as ws:
        await cleared.wait()
        deadline = time.monotonic() + RECOVERY_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic()))
            except (asyncio.TimeoutError, ConnectionClosed):
                return None
            if msg.get("type") == "trade" and float(msg.get("time") or 0) > cleared_at[0]:
                return time.time() - cleared_at[0]
    return None


async def run_scenario(name):
    if not await rows_since(utcnow() - timedelta(seconds=30)):
        raise RuntimeError("no trades in the last 30 s; the pipeline isn't flowing")
    print(f"[{name}] baseline {BASELINE_S}s")
    await asyncio.sleep(BASELINE_S)
    errors_before = send_errors_now()
    extra, outage = {}, 0
    t_fault = utcnow()
    print(f"[{name}] fault")
    if name == "taskmanager":
        docker("restart", "flink-taskmanager")
    elif name == "kafka":
        docker("restart", "kafka")
    elif name == "postgres":
        docker("stop", "postgres")
        stopped_containers.add("postgres")
        await asyncio.sleep(OUTAGE_S)
        docker("start", "postgres")
        stopped_containers.discard("postgres")
        outage = OUTAGE_S
    elif name == "redis":
        stop_probe, cleared, cleared_at = asyncio.Event(), asyncio.Event(), [0.0]
        probe = asyncio.create_task(probe_latest(stop_probe))
        ws_task = asyncio.create_task(first_trade_after(cleared, cleared_at))
        await asyncio.sleep(2)  # let the WS client connect before Redis goes away
        docker("stop", "redis")
        stopped_containers.add("redis")
        await asyncio.sleep(OUTAGE_S)
        docker("start", "redis")
        stopped_containers.discard("redis")
        cleared_at[0] = time.time()
        cleared.set()
        outage = OUTAGE_S
        await asyncio.sleep(10)
        stop_probe.set()
        extra["api_probe"] = await probe
        extra["ws_trade_resumed_seconds"] = await ws_task
    elif name == "producer":
        restart_producer()
    t_cleared = utcnow()

    t_recovered = await wait_recovered(t_cleared)
    print(f"[{name}] recovered={t_recovered is not None}; settling {SETTLE_S}s")
    flink = flink_running()
    await asyncio.sleep(SETTLE_S)

    t0 = t_fault - timedelta(seconds=60)
    t1 = (t_recovered or utcnow()) + timedelta(seconds=60)
    gaps = await query("SELECT * FROM chaos_gaps($1, $2)", t0, t1)
    mismatches = await query("SELECT * FROM chaos_candle_mismatches($1, $2)", t0, t1)
    return {
        "name": name,
        "t_fault": t_fault,
        "t_cleared": t_cleared,
        "t_recovered": t_recovered,
        "recovered": t_recovered is not None,
        "recovery_seconds": (t_recovered - t_fault).total_seconds() if t_recovered else None,
        "outage_seconds": outage,
        "gaps_by_symbol": {r["symbol"]: r["gaps"] for r in gaps},
        "gaps_total": sum(r["gaps"] for r in gaps),
        "candle_mismatches": [dict(r) for r in mismatches],
        "send_errors_delta": send_errors_delta(errors_before, send_errors_now()),
        "flink_running": flink,
    } | extra


async def run(names):
    conn = await asyncpg.connect(**POSTGRES_CONNECT_KWARGS)
    try:
        await conn.execute(CHECKS_SQL)
    finally:
        await conn.close()
    results = []
    for name in names:
        try:
            results.append(await run_scenario(name))
        except Exception as e:  # record and move on; restore happens in main()'s finally
            print(f"[{name}] ERROR {e}")
            results.append({"name": name, "error": str(e), "recovered": False})
            for c in list(stopped_containers):
                docker("start", c)
                stopped_containers.discard(c)
    return results


def summarize(results):
    print("\nscenario      recovered  recovery s  gaps  candle mismatches  send_errors")
    for r in results:
        rec = "-" if r.get("recovery_seconds") is None else f"{r['recovery_seconds']:.1f}"
        print(f"{r['name']:<13} {str(r.get('recovered')):<10} {rec:>10}  {r.get('gaps_total', '-'):>4}  "
              f"{len(r.get('candle_mismatches', [])):>17}  {r.get('send_errors_delta', '-')}")
        if "api_probe" in r:
            print(f"              API availability {r['api_probe']['availability']}, sources {r['api_probe']['sources']}, "
                  f"WS trades resumed after {r['ws_trade_resumed_seconds']}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=SCENARIOS, action="append", help="run just these scenarios")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    assert_local_stack()
    started = utcnow()
    try:
        with api_server(reuse=True):
            results = asyncio.run(run(args.only or SCENARIOS))
    finally:
        for c in list(stopped_containers):
            print(f"restoring {c}")
            docker("start", c)
        if producer_killed and not producer_pids():
            print("restarting the producer")
            start_producer()
    summarize(results)
    if not args.no_save:
        path = write_results("chaos", {"started": started, "conditions": run_conditions(), "scenarios": results})
        print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-run one short scenario**

Precondition: the stack is up and the producer is running.

Run: `venv/bin/python -m benchmarks.chaos_test --only redis --no-save`
Expected (about 5 minutes):
- the table prints with `recovered True` and `gaps 0`;
- the API availability line shows `availability` near 1.0 and a `postgres` count in the sources;
- `WS trades resumed after <number>s`.

If `availability` is well below 1.0, **stop and report it**. It means the Redis-down fallback doesn't hold, which is a real finding for the spec's Known limitations. Don't paper over it.

- [ ] **Step 3: Check that Ctrl-C restores the stack**

Run `venv/bin/python -m benchmarks.chaos_test --only postgres --no-save`. When it prints `[postgres] fault`, press Ctrl-C within 30 s.
Expected: the script prints `restoring postgres`, and `docker ps --filter name=postgres --format '{{.Status}}'` shows `Up`.

- [ ] **Step 4: Run the unit tests, then commit**

Run: `venv/bin/python -m pytest -q` (expect 85 passed)

```bash
git add benchmarks/chaos_test.py
git commit -m "feat(benchmarks): chaos test for TaskManager, Kafka, Postgres, Redis and producer failures"
```

---

### Task 5: Full runs, committed results, README

**Files:**
- Create: `benchmarks/results/<date>-load.json`, `benchmarks/results/<date>-chaos.json` (generated)
- Modify: `README.md` (the "Results" table, "Known limitations", and a short "Benchmarks" section)

- [ ] **Step 1: Full load test.** With the stack up and nothing on :8000, run `make load-test` (about 9 minutes). Keep the printed summary.

- [ ] **Step 2: Full chaos test.** Start `make api` in another terminal (scenario 4 needs the API; the chaos test reuses a running one), then run `make chaos-test` (about 25 minutes). Keep the printed summary.

- [ ] **Step 3: Update `README.md`.** Replace the "Results" table with the one below. Every value comes from the two JSON files; copy it, don't round it favourably. A row whose number is missing because the test failed says so.

```markdown
| What | Result |
|---|---|
| Trades ingested | 17,969, with 0 duplicates and 0 missed (38-min acceptance run) |
| REST latency | p95 **<p95 at 50 clients> ms** at 50 concurrent clients, all endpoints ([load results](benchmarks/results/<date>-load.json)) |
| Live WebSocket fan-out | **<max_clients_at_99pct_delivery> clients** at ≥ 99% delivery, p95 exchange-to-client lag **<lag> ms** |
| Ingestion lag | p95 **<ingestion p95> ms** from exchange trade time to producer |
| Flink TaskManager crash | recovered in **<s> s**, <gaps> lost trades, <n> inconsistent candles ([chaos results](benchmarks/results/<date>-chaos.json)) |
| Kafka broker restart | recovered in <s> s, **<gaps> lost trades** (see Known limitations) |
| Postgres down 30 s | recovered in <s> s after restart, <gaps> lost trades, <n> inconsistent candles |
| Redis down 30 s | API <availability as %> available (served from Postgres), live trades resumed <s> s after restart |
| Producer restart | <gaps> trades missed while it reconnected (no replay from Coinbase yet) |
| Anomaly alert | Injected price jump detected at z = 63.3, delivered exactly once to Postgres and Kafka |
```

Add a short section before "Tests":

```markdown
## Benchmarks

`make load-test` and `make chaos-test` reproduce the numbers above against the local stack and write the JSON files in [`benchmarks/results/`](benchmarks/results/). Conditions are recorded in each file: load generator and stack on the same laptop, a single API process, and exchange-to-client lag that includes the Coinbase network delay.
```

Under "Known limitations", add the measured Kafka-restart result. For example, if `send_errors_delta > 0`: "A Kafka broker restart loses the trades sent while it's down (<n> in the chaos run): the producer's retry budget (5 retries, 100 ms backoff) is shorter than a broker restart. The fix is a longer retry budget or a local replay buffer." If the run lost nothing, say that instead and remove the caveat.

- [ ] **Step 4: Check and commit**

Run: `venv/bin/python -m pytest -q` and `git status` (the two JSON files must show up as untracked, which proves the `.gitignore` exception works).

```bash
git add benchmarks/results/*.json README.md
git commit -m "docs: measured load and chaos results in README"
```
