# Analytics Layer (backfill + dbt + Airflow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Load 90 days of Coinbase candles and repair trade gaps exactly.
- Model everything in dbt: staging → intermediate → marts, with tests, unit tests and docs.
- Run it hourly from an Airflow DAG, where each dbt model is its own task.

**Architecture:**
- A `src/backfill/` package writes to TimescaleDB:
  - a throttled, retrying Coinbase REST client;
  - a candle loader;
  - a gap repairer that reuses the lite consumer's candle recompute SQL.
- An `analytics/` dbt project reads those tables. dbt runs in the main venv.
- Airflow 3.3 runs in its own venv. The DAG calls the backfill through `venv/bin/python` and dbt through Cosmos with an explicit `dbt_executable_path`.

**Tech Stack:** Python 3.12, httpx, psycopg2, dbt-core 1.12.5, dbt-postgres 1.11.0, dbt_utils, apache-airflow 3.3.2, astronomer-cosmos 1.15.1, TimescaleDB.

**Spec:** `docs/superpowers/specs/2026-09-27-analytics-layer-design.md`

## Global Constraints

- Commits carry no `Co-Authored-By` or "Generated with" lines (`CLAUDE.md`).
- Coinbase is called at 5 requests/s at most. A 429 or 5xx is retried with backoff from 1 s up to 30 s, 5 attempts. Any other 4xx is raised.
- A candle request covers `[s, s + 299 min]`: both ends are inclusive and the API maximum is 300 buckets (verified live). The next window starts at `s + 300 min`.
- A trade page is `after=<id>`, which returns `trade_id < id`, newest first. The next cursor is the `cb-after` header.
- REST `side` is stored **unchanged**. Task 4 checks this against live data.
- Gap repair only looks at the last 7 days, and skips any gap with more than 10,000 missing ids.
- Pipeline vs exchange agreement: `abs(close_diff_pct) <= 0.05 AND abs(volume_ratio - 1) <= 0.05`.
- Signals: previous 60 returns, at least 30 of them, `volume > 0`, fire when `|z| > 4`. Severity is LOW 4–6, MEDIUM 6–8, HIGH ≥ 8. Direction comes from the sign of the return.
- dbt objects live in schema `analytics`. Sources are in schema `public`.
- The Airflow venv is `.venv-airflow`, `AIRFLOW_HOME` is `airflow/`, and only `airflow/dags/` is committed.

## Review Focus

1. **A fresh volume where the migration runs before `init-db.sql`.** The mount name must sort after `init-db.sql`, so Task 1 uses `zz-analytics.sql`. Pinned in Task 1 Step 5 by checking the order.
2. **A re-run of `make backfill` right after a full run** must fetch only the last minute's window, never 90 days again. Pinned in Task 2 (`test_resume_starts_one_minute_before_last_bucket`).
3. **An empty trades page, or a cursor that stops moving** (Coinbase returns nothing older) must end the gap fetch, not loop forever. Pinned in Task 3 (`test_fetch_gap_stops_on_empty_page`).
4. **A minute with a missing return next to a real return**, for example the first candle after a gap. It must never produce a signal or a clustering pair. Pinned in Task 5's `int_returns_1m` unit test.
5. **The repair recomputes a minute that Flink has already written.** The recompute must upsert: overwrite with the complete candle, never add a duplicate. Pinned in Task 3's test, which asserts the SQL is the shared `ON CONFLICT ... DO UPDATE` statement.

---

### Task 1: Migration, shared candle SQL, schema checks in CI

**Files:**
- Create: `configs/migrations/001_analytics.sql`
- Create: `tests/sql/analytics_schema_checks.sql`
- Create: `src/candle_sql.py`
- Modify: `src/consumers/simple_consumer.py`, to import the SQL instead of defining it
- Modify: `docker-compose.yml` (the postgres volumes)
- Modify: `.github/workflows/ci.yml` (the `schema` job)
- Modify: `Makefile` (the `migrate` target)

**Interfaces:**
- Produces:
  - `src.candle_sql.CANDLE_UPSERT_FROM_RAW_SQL`, psycopg2 SQL with parameters `(window_start, window_end, symbol, window_start, window_end)`;
  - table `coinbase_candles_1m(crypto_id, bucket, open, high, low, close, volume, loaded_at)`;
  - `raw_trades.source`;
  - `raw_trades.sequence`, now nullable.

- [ ] **Step 1: Write the failing SQL check** (`tests/sql/analytics_schema_checks.sql`)

```sql
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
```

- [ ] **Step 2: Run it and confirm it fails.** Use a throwaway `timescale/timescaledb:latest-pg15` container named `analytics-sql-check`, with `init-db.sql` applied.
Expected: `ERROR: coinbase_candles_1m missing`

- [ ] **Step 3: Write the migration** (`configs/migrations/001_analytics.sql`)

```sql
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
```

- [ ] **Step 4: Apply the migration twice, then run the check.**
Expected: `analytics_schema_checks: ALL PASSED`

- [ ] **Step 5: Move the candle SQL into `src/candle_sql.py`, and wire up compose, CI and Make.**
- **`src/candle_sql.py`:** contains the module docstring `"""Candle recompute from raw_trades, shared by the lite consumer and the trade-gap repair."""`, followed by the comment block and `CANDLE_UPSERT_FROM_RAW_SQL`, copied verbatim from `simple_consumer.py` (renamed without the leading underscore).
- **`simple_consumer.py`:** replace the definition with `from src.candle_sql import CANDLE_UPSERT_FROM_RAW_SQL as _CANDLE_UPSERT_FROM_RAW_SQL`, so existing tests and callers are unchanged.
- **`docker-compose.yml`, postgres `volumes`:** add `- ./configs/migrations/001_analytics.sql:/docker-entrypoint-initdb.d/zz-analytics.sql`. Check the order with `python3 -c "print(sorted(['init-db.sql','zz-analytics.sql']))"`; `init-db.sql` must be first.
- **CI `schema` job:** after the `init-db.sql` step, add the migration step twice (to check idempotency), and add `analytics_schema_checks.sql` after the chaos checks:

```yaml
      - run: psql -v ON_ERROR_STOP=1 -q -f configs/migrations/001_analytics.sql
      - run: psql -v ON_ERROR_STOP=1 -q -f configs/migrations/001_analytics.sql # idempotent
```

```yaml
      - run: psql -v ON_ERROR_STOP=1 -q -f tests/sql/analytics_schema_checks.sql
```

- **Makefile:** add `migrate` to `.PHONY`, and add:

```make
migrate: ## Apply configs/migrations/*.sql to the running postgres container (idempotent)
	docker exec -i postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -v ON_ERROR_STOP=1 -q' < configs/migrations/001_analytics.sql
```

- [ ] **Step 6: Run the suite and commit**

Run: `venv/bin/python -m pytest -q` (expect 94 passed)

```bash
git add configs/migrations tests/sql/analytics_schema_checks.sql src/candle_sql.py src/consumers/simple_consumer.py docker-compose.yml .github/workflows/ci.yml Makefile
git commit -m "feat(db): analytics migration (coinbase_candles_1m, raw_trades.source) and shared candle SQL"
```

---

### Task 2: Coinbase REST client and candle backfill

**Files:**
- Create: `src/backfill/__init__.py` (empty)
- Create: `src/backfill/coinbase.py`
- Create: `src/backfill/candles.py`
- Test: `tests/backfill/test_coinbase.py`
- Test: `tests/backfill/test_candles.py`

**Interfaces:**
- Produces:
  - `CoinbaseRest(client=None, rate_per_s=5.0, attempts=5, sleep=time.sleep, clock=time.monotonic)`, with the methods `.candles(product, start, end) -> list[list]` and `.trades_page(product, after) -> tuple[list[dict], int | None]`;
  - `candle_windows(start, end) -> Iterator[tuple[datetime, datetime]]`;
  - `parse_candle(row) -> tuple[datetime, Decimal, Decimal, Decimal, Decimal, Decimal]`, which returns `(bucket, open, high, low, close, volume)`;
  - `candle_start(last_bucket, end) -> datetime`;
  - `backfill_candles(conn, api, now=None) -> dict[str, int]`.

- [ ] **Step 1: Write the failing tests.**

`tests/backfill/test_coinbase.py`:

```python
import httpx
import pytest

from src.backfill.coinbase import CoinbaseRest


def make_api(handler, **kw):
    sleeps = []
    api = CoinbaseRest(
        client=httpx.Client(base_url="https://api.test", transport=httpx.MockTransport(handler)),
        sleep=sleeps.append, clock=lambda: 0.0, **kw,
    )
    return api, sleeps


def test_retries_429_then_succeeds():
    calls = []

    def handler(request):
        calls.append(request.url.params["after"])
        return httpx.Response(429) if len(calls) == 1 else httpx.Response(
            200, json=[{"trade_id": 9}], headers={"cb-after": "9"})

    api, sleeps = make_api(handler)
    page, cursor = api.trades_page("BTC-USD", after=10)
    assert page == [{"trade_id": 9}] and cursor == 9
    assert len(calls) == 2 and 1 in sleeps  # 1 s backoff after the 429


def test_other_4xx_is_raised_without_retry():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={"message": "bad"})

    api, _ = make_api(handler)
    with pytest.raises(httpx.HTTPStatusError):
        api.candles("BTC-USD", __import__("datetime").datetime(2026, 9, 1), __import__("datetime").datetime(2026, 9, 1))
    assert len(calls) == 1


def test_gives_up_after_the_attempt_budget():
    api, _ = make_api(lambda request: httpx.Response(503), attempts=3)
    with pytest.raises(httpx.HTTPStatusError):
        api.trades_page("BTC-USD", after=10)
```

`tests/backfill/test_candles.py`:

```python
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.backfill.candles import HISTORY, candle_start, candle_windows, parse_candle

T = datetime(2026, 9, 20, tzinfo=timezone.utc)
M = timedelta(minutes=1)


def test_windows_cover_300_buckets_each_with_inclusive_ends():
    assert list(candle_windows(T, T + 600 * M)) == [(T, T + 299 * M), (T + 300 * M, T + 599 * M)]


def test_windows_clip_the_last_window_to_end():
    windows = list(candle_windows(T, T + 650 * M))
    assert len(windows) == 3 and windows[-1] == (T + 600 * M, T + 650 * M)


def test_no_windows_when_start_is_not_before_end():
    assert list(candle_windows(T, T)) == []


def test_resume_starts_one_minute_before_last_bucket():
    assert candle_start(T, T + 60 * M) == T - M


def test_first_run_starts_90_days_back():
    assert candle_start(None, T) == T - HISTORY


def test_parse_candle_maps_coinbase_column_order():
    # Coinbase rows are [time, low, high, open, close, volume]
    row = [int(T.timestamp()), 99.5, 101.25, 100, 101, 2.5]
    assert parse_candle(row) == (T, Decimal("100"), Decimal("101.25"), Decimal("99.5"), Decimal("101"), Decimal("2.5"))
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `venv/bin/python -m pytest tests/backfill -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'src.backfill'`

- [ ] **Step 3: Implement.**

`src/backfill/coinbase.py`:

```python
"""Coinbase Exchange public REST client: throttled to a steady rate, retrying 429/5xx with backoff."""

import logging
import time

import httpx

API_URL = "https://api.exchange.coinbase.com"
RETRY_STATUSES = {429, 500, 502, 503, 504}
logger = logging.getLogger(__name__)


class CoinbaseRest:
    def __init__(self, client=None, rate_per_s=5.0, attempts=5, sleep=time.sleep, clock=time.monotonic):
        self.client = client or httpx.Client(base_url=API_URL, timeout=10)
        self.min_interval = 1.0 / rate_per_s
        self.attempts = attempts
        self.sleep, self.clock = sleep, clock
        self._last_request = float("-inf")

    def _get(self, path, params):
        error = None
        for attempt in range(self.attempts):
            wait = self._last_request + self.min_interval - self.clock()
            if wait > 0:
                self.sleep(wait)
            self._last_request = self.clock()
            try:
                response = self.client.get(path, params=params)
            except httpx.TransportError as e:
                error = e
            else:
                if response.status_code not in RETRY_STATUSES:
                    response.raise_for_status()  # other 4xx: a bug in our request, don't retry
                    return response
                error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}", request=response.request, response=response)
            if attempt < self.attempts - 1:
                backoff = min(2 ** attempt, 30)
                logger.warning("Coinbase %s failed (%s); retrying in %ss", path, error, backoff)
                self.sleep(backoff)
        raise error

    def candles(self, product, start, end):
        """1-minute candles in [start, end] (both inclusive, <= 300 buckets), newest first."""
        params = {"granularity": 60, "start": start.isoformat(), "end": end.isoformat()}
        return self._get(f"/products/{product}/candles", params).json()

    def trades_page(self, product, after):
        """Up to 1000 trades with trade_id < after, newest first, plus the cursor for the next page."""
        response = self._get(f"/products/{product}/trades", {"limit": 1000, "after": after})
        cursor = response.headers.get("cb-after")
        return response.json(), int(cursor) if cursor else None
```

`src/backfill/candles.py`:

```python
"""Loads official Coinbase 1-minute candles into coinbase_candles_1m (90 days, then incremental)."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)

MINUTE = timedelta(minutes=1)
WINDOW = 300 * MINUTE  # one request spans [s, s + 299 min]: 300 buckets, the API maximum
HISTORY = timedelta(days=90)

SYMBOLS_SQL = "SELECT id, symbol, coinbase_product FROM cryptocurrencies WHERE is_active ORDER BY symbol"
LAST_BUCKET_SQL = "SELECT max(bucket) FROM coinbase_candles_1m WHERE crypto_id = %s"
UPSERT_SQL = """
INSERT INTO coinbase_candles_1m (crypto_id, bucket, open, high, low, close, volume) VALUES %s
ON CONFLICT (crypto_id, bucket) DO UPDATE SET
    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
    close = EXCLUDED.close, volume = EXCLUDED.volume, loaded_at = now()
"""


def candle_windows(start, end):
    s = start
    while s < end:
        yield s, min(s + WINDOW - MINUTE, end)
        s += WINDOW


def candle_start(last_bucket, end):
    """Re-fetch the last (possibly partial) minute on resume; 90 days back on a first run."""
    return last_bucket - MINUTE if last_bucket else end - HISTORY


def parse_candle(row):
    t, low, high, open_, close, volume = row
    d = lambda x: Decimal(str(x))  # noqa: E731 -- str() keeps the API's exact decimal digits
    return datetime.fromtimestamp(t, tz=timezone.utc), d(open_), d(high), d(low), d(close), d(volume)


def backfill_candles(conn, api, now=None):
    end = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    with conn.cursor() as cur:
        cur.execute(SYMBOLS_SQL)
        symbols = cur.fetchall()
    loaded = {}
    for crypto_id, symbol, product in symbols:
        with conn.cursor() as cur:
            cur.execute(LAST_BUCKET_SQL, (crypto_id,))
            start = candle_start(cur.fetchone()[0], end)
        n = 0
        for s, e in candle_windows(start, end):
            rows = [(crypto_id, *parse_candle(r)) for r in api.candles(product, s, e)]
            if rows:
                with conn.cursor() as cur:
                    execute_values(cur, UPSERT_SQL, rows)
                conn.commit()
                n += len(rows)
        loaded[symbol] = n
        logger.info("candles %s: %d rows from %s", symbol, n, start.isoformat())
    return loaded
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `venv/bin/python -m pytest tests/backfill -q`, then the full suite.
Expected: 9 passed, then 103 passed.

- [ ] **Step 5: Commit**

```bash
git add src/backfill tests/backfill
git commit -m "feat(backfill): throttled Coinbase REST client and incremental 1-minute candle backfill"
```

---

### Task 3: Trade-gap repair

**Files:**
- Create: `src/backfill/trade_gaps.py`
- Test: `tests/backfill/test_trade_gaps.py`

**Interfaces:**
- Consumes:
  - `CoinbaseRest.trades_page` (from Task 2);
  - `CANDLE_UPSERT_FROM_RAW_SQL` (from Task 1).
- Produces:
  - `select_missing(page, prev_id, next_id) -> list[dict]`;
  - `fetch_gap(api, product, prev_id, next_id) -> list[dict]`;
  - `repair_gaps(conn, api) -> dict` with the keys `gaps_found`, `gaps_repaired`, `gaps_skipped`, `trades_inserted`, `minutes_recomputed`;
  - `MAX_GAP = 10_000`.

- [ ] **Step 1: Write the failing tests** (`tests/backfill/test_trade_gaps.py`)

```python
from datetime import datetime, timezone

import httpx

from src.backfill.coinbase import CoinbaseRest
from src.backfill.trade_gaps import MAX_GAP, fetch_gap, repair_gaps, select_missing
from src.candle_sql import CANDLE_UPSERT_FROM_RAW_SQL


def trade(i, second=0, side="buy"):
    return {"trade_id": i, "side": side, "size": "0.5", "price": "100.0",
            "time": f"2026-09-27T07:50:{second:02d}.000000Z"}


def api_with_pages(pages):
    """pages: {after: (trades, cb_after)}; records every `after` requested."""
    requested = []

    def handler(request):
        after = int(request.url.params["after"])
        requested.append(after)
        trades, cursor = pages.get(after, ([], None))
        headers = {"cb-after": str(cursor)} if cursor is not None else {}
        return httpx.Response(200, json=trades, headers=headers)

    client = httpx.Client(base_url="https://api.test", transport=httpx.MockTransport(handler))
    return CoinbaseRest(client=client, sleep=lambda s: None, clock=lambda: 0.0), requested


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.calls.append(("execute", sql, params))

    def executemany(self, sql, rows):
        self.conn.calls.append(("executemany", sql, list(rows)))

    def fetchall(self):
        return self.conn.gaps


class FakeConn:
    def __init__(self, gaps):
        self.gaps, self.calls, self.commits = gaps, [], 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


def test_select_missing_keeps_only_ids_strictly_inside_the_gap():
    page = [trade(103), trade(102), trade(101), trade(100)]
    assert [t["trade_id"] for t in select_missing(page, prev_id=100, next_id=103)] == [102, 101]


def test_fetch_gap_pages_until_it_reaches_the_trade_before_the_gap():
    api, requested = api_with_pages({103: ([trade(102)], 102), 102: ([trade(101), trade(100)], 100)})
    assert [t["trade_id"] for t in fetch_gap(api, "BTC-USD", 100, 103)] == [102, 101]
    assert requested == [103, 102]


def test_fetch_gap_stops_on_empty_page():
    api, requested = api_with_pages({})
    assert fetch_gap(api, "BTC-USD", 100, 103) == []
    assert requested == [103]


def test_repair_inserts_missing_trades_and_recomputes_their_minute():
    api, _ = api_with_pages({103: ([trade(102, 5, "sell")], 102), 102: ([trade(101, 7), trade(100)], 100)})
    conn = FakeConn(gaps=[(1, "BTC", "BTC-USD", 100, 103)])
    report = repair_gaps(conn, api)
    assert report == {"gaps_found": 1, "gaps_repaired": 1, "gaps_skipped": 0,
                      "trades_inserted": 2, "minutes_recomputed": 1}
    inserted = next(rows for kind, _, rows in conn.calls if kind == "executemany")
    assert [(r[1], r[4], r[5]) for r in inserted] == [(102, "sell", None), (101, "buy", None)]  # side unchanged
    recomputes = [c for c in conn.calls if c[1] == CANDLE_UPSERT_FROM_RAW_SQL]
    minute = datetime(2026, 9, 27, 7, 50, tzinfo=timezone.utc)
    assert len(recomputes) == 1 and recomputes[0][2][0] == minute and recomputes[0][2][2] == "BTC"


def test_gap_larger_than_the_cap_is_skipped_without_any_request():
    api, requested = api_with_pages({})
    conn = FakeConn(gaps=[(1, "BTC", "BTC-USD", 100, 100 + MAX_GAP + 2)])
    report = repair_gaps(conn, api)
    assert report["gaps_skipped"] == 1 and report["trades_inserted"] == 0 and requested == []
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `venv/bin/python -m pytest tests/backfill/test_trade_gaps.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'src.backfill.trade_gaps'`

- [ ] **Step 3: Implement** (`src/backfill/trade_gaps.py`)

```python
"""Repairs raw_trades gaps (producer restarts) from the Coinbase REST trades endpoint, by trade_id.

Coinbase trade_ids rise by exactly 1 per product, so a jump is an exact list of missing trades.
Each repaired minute's candle is recomputed from raw_trades with the lite consumer's shared SQL.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from src.candle_sql import CANDLE_UPSERT_FROM_RAW_SQL

logger = logging.getLogger(__name__)

MAX_GAP = 10_000
MINUTE = timedelta(minutes=1)

GAPS_SQL = """
SELECT g.crypto_id, c.symbol, c.coinbase_product, g.prev_id, g.trade_id
FROM (
    SELECT crypto_id, trade_id,
           lag(trade_id) OVER (PARTITION BY crypto_id ORDER BY trade_id) AS prev_id
    FROM raw_trades
    WHERE event_time > now() - INTERVAL '7 days'
) g
JOIN cryptocurrencies c ON c.id = g.crypto_id
WHERE g.trade_id - g.prev_id > 1
ORDER BY c.symbol, g.prev_id
"""

INSERT_SQL = """
INSERT INTO raw_trades (crypto_id, trade_id, price, size, side, sequence, event_time, ingest_time, source)
VALUES (%s, %s, %s, %s, %s, %s, %s, now(), 'rest_backfill')
ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING
"""


def select_missing(page, prev_id, next_id):
    return [t for t in page if prev_id < t["trade_id"] < next_id]


def fetch_gap(api, product, prev_id, next_id):
    found, after = [], next_id
    while after is not None:
        page, cursor = api.trades_page(product, after)
        found += select_missing(page, prev_id, next_id)
        if not page or min(t["trade_id"] for t in page) <= prev_id + 1 or cursor is None or cursor >= after:
            break
        after = cursor
    return found


def _row(crypto_id, t):
    event_time = datetime.fromisoformat(t["time"].replace("Z", "+00:00"))
    # REST `side` is the maker side, the same meaning as the matches channel: stored unchanged.
    return (crypto_id, t["trade_id"], Decimal(t["price"]), Decimal(t["size"]), t["side"], None, event_time)


def repair_gaps(conn, api):
    report = {"gaps_found": 0, "gaps_repaired": 0, "gaps_skipped": 0, "trades_inserted": 0, "minutes_recomputed": 0}
    with conn.cursor() as cur:
        cur.execute(GAPS_SQL)
        gaps = cur.fetchall()
    for crypto_id, symbol, product, prev_id, next_id in gaps:
        report["gaps_found"] += 1
        missing = next_id - prev_id - 1
        if missing > MAX_GAP:
            logger.warning("%s: gap of %d trades after %d exceeds %d; skipped", symbol, missing, prev_id, MAX_GAP)
            report["gaps_skipped"] += 1
            continue
        rows = [_row(crypto_id, t) for t in fetch_gap(api, product, prev_id, next_id)]
        minutes = sorted({r[6].replace(second=0, microsecond=0) for r in rows})
        with conn.cursor() as cur:
            if rows:
                cur.executemany(INSERT_SQL, rows)
            for m in minutes:
                cur.execute(CANDLE_UPSERT_FROM_RAW_SQL, (m, m + MINUTE, symbol, m, m + MINUTE))
        conn.commit()
        report["trades_inserted"] += len(rows)
        report["minutes_recomputed"] += len(minutes)
        if len(rows) == missing:
            report["gaps_repaired"] += 1
        else:
            logger.warning("%s: gap after %d: fetched %d of %d missing trades", symbol, prev_id, len(rows), missing)
    logger.info("trade gaps: %s", report)
    return report
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `venv/bin/python -m pytest tests/backfill -q`, then the full suite.
Expected: 14 passed, then 108 passed.

- [ ] **Step 5: Commit**

```bash
git add src/backfill/trade_gaps.py tests/backfill/test_trade_gaps.py
git commit -m "feat(backfill): exact trade-gap repair by trade_id with candle recompute"
```

---

### Task 4: CLI, Make target, live backfill

**Files:**
- Create: `src/backfill/__main__.py`
- Modify: `Makefile` (`backfill`)

- [ ] **Step 1: Write `src/backfill/__main__.py`**

```python
"""python -m src.backfill [candles|gaps|all] — see src/backfill/candles.py and trade_gaps.py."""

import argparse
import logging

import psycopg2

from src.backfill.candles import backfill_candles
from src.backfill.coinbase import CoinbaseRest
from src.backfill.trade_gaps import repair_gaps
from src.config import LOG_LEVEL, POSTGRES_CONNECT_KWARGS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("what", nargs="?", choices=["candles", "gaps", "all"], default="all")
    args = parser.parse_args(argv)
    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    conn = psycopg2.connect(**POSTGRES_CONNECT_KWARGS)
    api = CoinbaseRest()
    try:
        if args.what in ("candles", "all"):
            print("candles loaded:", backfill_candles(conn, api))
        if args.what in ("gaps", "all"):
            print("trade gaps:", repair_gaps(conn, api))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add the Makefile target** (add `backfill` to `.PHONY`)

```make
backfill: ## Load 90 days of Coinbase 1-minute candles (then incremental) and repair trade gaps
	$(PYTHON_CMD) -m src.backfill all
```

- [ ] **Step 3: Live run.** Start the stack without the frontend (port 3000 belongs to another app). Then:
  - run `make migrate`;
  - start the producer and deploy Flink;
  - run `make backfill` and time it.

Expected:
- about 1.04 M candles in total (`SELECT count(*) FROM coinbase_candles_1m`);
- a second `make backfill` loads only a few rows per symbol (the resume check);
- the gap report prints, and any gap with at most 10,000 missing trades is repaired.

- [ ] **Step 4: Check the `side` meaning against live data.** Fetch one REST trades page for BTC-USD and join it on `trade_id` with `raw_trades` rows where `source='stream'`.
Expected: `side` matches for 100% of overlapping ids. If it doesn't, stop and flip it in `_row`, adding a test and a ruling.

- [ ] **Step 5: Commit**

```bash
git add src/backfill/__main__.py Makefile
git commit -m "feat(backfill): CLI and make backfill"
```

---

### Task 5: dbt project

**Files:**
- Create: `requirements-analytics.txt`
- Create: `analytics/dbt_project.yml`, `analytics/packages.yml`, `analytics/profiles.yml`
- Create: `analytics/models/staging/{sources.yml,_staging.yml,stg_symbols.sql,stg_trades.sql,stg_pipeline_candles.sql,stg_exchange_candles.sql,stg_alerts.sql}`
- Create: `analytics/models/intermediate/{_intermediate.yml,int_candles_unified.sql,int_returns_1m.sql}`
- Create: `analytics/models/marts/{_marts.yml,exposures.yml,fct_candles_1m.sql,mart_volatility_hourly.sql,mart_seasonality.sql,mart_signals.sql,mart_signal_precision.sql,mart_pipeline_vs_exchange.sql,mart_pipeline_vs_exchange_summary.sql}`
- Create: `analytics/tests/{assert_ohlc_bounds.sql,assert_no_future_buckets.sql,assert_signals_after_warmup.sql}`
- Create: `tests/sql/analytics_fixture.sql`
- Modify: `Makefile` (`dbt`, `dbt-docs`), `.gitignore`, `.github/workflows/ci.yml` (the `analytics` job)

The full file contents are written in Step 3 below; there are too many small SQL and YAML files to repeat here. The logic of each model is fixed by the spec's Section 2 table and this plan's Global Constraints. Unit tests are the RED gate: Step 1 writes them first, and Step 2 runs `dbt test --select test_type:unit`, which must fail because the models don't exist yet.

- [ ] **Step 1: Install dbt, scaffold `dbt_project.yml`, `packages.yml` and `profiles.yml`, and write the unit tests** (in `_intermediate.yml` and `_marts.yml`):
  - `int_candles_unified`: the pipeline wins when both exist; the exchange fills in when the pipeline is missing; `source` is labeled.
  - `int_returns_1m`: for candles at t, t+1 and t+3, the returns are `null`, `ln(c1/c0)`, `null`.
  - `mart_signals`: symbol 1 gets 40 alternating closes (100 and 100.01) and then a jump to 101 at minute 40, which gives 1 HIGH PRICE_SPIKE row. Symbol 2 gets the same jump at minute 10, inside the warm-up, which gives no row.
- [ ] **Step 2: Run the unit tests and confirm they fail** (`dbt build --select +int_candles_unified` etc. fails on the missing models).
- [ ] **Step 3: Write the staging, intermediate and mart models, the singular tests, and the docs YAML** as the spec describes. Materializations: staging and intermediate are views, `fct_candles_1m` is incremental with a 2-hour lookback, and marts are tables.
- [ ] **Step 4: Write `tests/sql/analytics_fixture.sql`:** 180 minutes of BTC and ETH candles in `coinbase_candles_1m`, the same values for minutes 60–179 in `price_aggregates_1m`, a jump to 101 at minute 120, an ETH pipeline mismatch at minute 90, and a BTC PRICE_SPIKE alert at minute 120. Load it into a throwaway TimescaleDB, then run `dbt build --target ci` against it.
Expected: every model, test and unit test passes; `mart_signals` has rows, one of them with `flink_alert = true`; the summary shows ETH `pct_agree < 1`.
- [ ] **Step 5: `make dbt` against the live database, with the 90-day history.**
Expected: `dbt build` is fully green. Record the row counts and the headline mart values in the ledger for Task 7.
- [ ] **Step 6: Add the CI `analytics` job, the Make targets and the `.gitignore` entries** (`.venv-airflow/`, `airflow/*`, `!airflow/dags/`, `analytics/dbt_packages/`), then commit.

```bash
git add requirements-analytics.txt analytics tests/sql/analytics_fixture.sql Makefile .gitignore .github/workflows/ci.yml
git commit -m "feat(analytics): dbt project with staging, marts, tests, unit tests and docs"
```

---

### Task 6: Airflow DAG

**Files:**
- Create: `airflow/dags/crypto_analytics.py`
- Modify: `Makefile` (`airflow-setup`, `airflow`), `.github/workflows/ci.yml` (the `airflow` job)

- [ ] **Step 1: `make airflow-setup`** (`python3.12 -m venv .venv-airflow`, then install Airflow 3.3.2 and Cosmos 1.15.1 with the constraints file).
- [ ] **Step 2: Write the DAG** as the spec's Section 3 describes: `BashOperator`s for the two backfill steps and a Cosmos `DbtTaskGroup` with `TestBehavior.AFTER_EACH`. Paths are derived from `__file__`.
- [ ] **Step 3: Confirm the DAG imports cleanly.** Run `AIRFLOW_HOME=$PWD/airflow .venv-airflow/bin/airflow dags list-import-errors`.
Expected: `No data found`. The RED gate is running this before the DAG file exists; the DAG must then appear in `airflow dags list`.
- [ ] **Step 4: Test one full run** with `airflow dags test crypto_analytics`.
Expected: every task succeeds, including one run and one test task per dbt model.
- [ ] **Step 5: Add the CI `airflow` job and commit.**

```bash
git add airflow/dags Makefile .github/workflows/ci.yml
git commit -m "feat(airflow): hourly crypto_analytics DAG (backfill -> gap repair -> dbt via Cosmos)"
```

---

### Task 7: README and results

- [ ] Update the Mermaid diagram, add an "Analytics" section, and add Results rows from the live run's numbers: candles modeled, `pct_agree`, signal precision at 15 minutes, gaps repaired, and Flink-matched signals. Update the test counts.
- [ ] Run the full pytest suite, push the branch, and check that all 6 CI jobs are green before merging.

```bash
git add README.md
git commit -m "docs: analytics layer in README with measured results"
```
