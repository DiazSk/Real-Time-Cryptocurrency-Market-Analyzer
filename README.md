# Real-Time Cryptocurrency Market Analyzer

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A streaming data pipeline that ingests **every trade** for 8 crypto pairs from Coinbase's public WebSocket feed, deduplicates and aggregates them into 1-minute OHLCV candles in event time with Apache Flink, flags statistically unusual moves with a z-score detector, and serves the results through FastAPI and a Next.js terminal. TimescaleDB continuous aggregates provide 5-minute, 15-minute and 1-hour rollups.

Tracks `BTC`, `ETH`, `SOL`, `XRP`, `ADA`, `DOGE`, `AVAX`, `POL` (Polygon; `MATIC-USD` is delisted on Coinbase). The list lives in one place: the `cryptocurrencies` table. Runs entirely in Docker.

---

## Architecture

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

### Key implementation details

| Concern | Implementation |
|---|---|
| TimescaleDB retention | Native `add_retention_policy`: 7 days for raw_trades, 90 days for candles and rollups |
| Async API drivers | `asyncpg` + `redis.asyncio`; connection pools stored on `app.state` via lifespan |
| Next.js data fetching | Server Components + `fetch` ISR for CoinGecko; TanStack Query for backend REST; `useCryptoSocket` for WS |
| Frontend WS resilience | Exponential-backoff reconnect (1 s → 30 s), 25 s ping, 60 s dead-frame timeout, validated WS envelope (`ws.ts` casts `data`) |
| Checkpointing | 30 s, EXACTLY_ONCE, RocksDB incremental, retained on cancel, shared flink_data volume |
| Dedup | Keyed last-seen trade_id per symbol (DedupByTradeId) + raw_trades primary key |
| Source validation | Flink's `TradeDeserializer` drops malformed JSON, Kafka tombstones and records with an invalid `side` at the source (`Trade.isValid`), so one bad record can't crash-loop the job |
| Anomaly detection | EWMA z-score of 1-min log returns, 30-candle warm-up, `trade_count ≥ 5`, \|z\| > 4, severity bands |
| Alert direction & severity | Direction (`PRICE_SPIKE` / `PRICE_DROP`) comes from the sign of the price move (close vs. previous close); severity comes from `\|z\|`: LOW 4–6, MEDIUM 6–8, HIGH ≥ 8 |

### Delivery guarantees

| Sink | Mechanism | Guarantee |
|---|---|---|
| `raw_trades` hypertable | JDBC batch, `ON CONFLICT (crypto_id, trade_id, event_time) DO NOTHING` | At-least-once delivery with idempotent writes, so effectively-once |
| `price_aggregates_1m` | JDBC upsert on `(crypto_id, window_start)` | Effectively-once |
| `price_alerts` | JDBC, unique `(crypto_id, window_start, alert_type)`, `DO NOTHING` | Effectively-once |
| Kafka `crypto-alerts` | `KafkaSink` `EXACTLY_ONCE`, `setTransactionalIdPrefix("crypto-alerts")`, producer property `transaction.timeout.ms=900000` | Exactly-once for `read_committed` consumers; visibility is delayed by up to one checkpoint interval |
| Redis `crypto:{SYM}:latest` + Pub/Sub `crypto:updates` | `SETEX` + `PUBLISH` | At-least-once. The overwrite is idempotent; clients dedupe on `window_start` |

### Known limitations

- The producer uses `kafka-python-ng`, which has no idempotent producer; a retried send can duplicate a trade in Kafka. Flink's `DedupByTradeId` and the `raw_trades` primary key remove those duplicates. Upgrade path: `confluent-kafka` with `enable.idempotence=true`.
- A minute with no trades produces no candle (no gap-filling yet).
- `/api/v1/trending` uses real-time aggregation (hourly buckets that include the current hour so far), but the 24h-ago comparison bucket still needs about 24-25 hours of candle history before results appear.
- A stateless restart (`deploy-flink-fresh`, or a job started without a savepoint) re-aggregates the in-progress minute from partial trades and resets the anomaly detector's 30-minute warm-up; the affected candle can be rebuilt from `raw_trades`.
- Any error frame from Coinbase stops the producer (by design for rejected subscriptions); rerun it after checking the log.
- Single Kafka broker and single TaskManager: this is a local development topology.

---

## Prerequisites

- Docker Desktop with Compose (≥ v2)
- Python 3.11–3.13 (3.12 recommended)
- Node.js 20+ (only needed if you run the Next.js terminal outside Docker)
- Java 11 or 17 + Maven (only needed to rebuild the Flink JAR)

**Minimum RAM:** 8 GB allocated to Docker (JobManager: 2 GB, TaskManager: 1.7 GB, plus Kafka/PostgreSQL/Redis).

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/Real-Time-Cryptocurrency-Market-Analyzer.git
cd Real-Time-Cryptocurrency-Market-Analyzer

cp .env.example .env
# Edit .env — at minimum set POSTGRES_PASSWORD and PGADMIN_PASSWORD

# Frontend env (only required if you'll run npm run dev locally)
cp frontend/.env.local.example frontend/.env.local  # or create one — see below
```

`frontend/.env.local` is read by Next.js and currently expects:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Server-side only — do NOT prefix with NEXT_PUBLIC_.
COINGECKO_BASE_URL=https://api.coingecko.com/api/v3
COINGECKO_API_KEY=           # optional, free-tier demo key
```

### 2. Install Python dependencies

```bash
python3.12 -m venv venv && venv/bin/pip install -r requirements.txt -r requirements-api.txt
```

### 3. Start the pipeline

```bash
bash scripts/start_pipeline.sh
```

This script: checks dependencies → loads `.env` → runs `docker-compose up -d` → waits for Kafka, PostgreSQL, and Redis to be healthy → creates the `crypto-trades` Kafka topic and starts the Coinbase producer in the background.

### 4. Deploy the Flink job

A pre-built JAR is not included. Build it first:

```bash
cd src/flink_jobs
mvn clean package -DskipTests
cd ../..
```

Then deploy:

```bash
# Copy JAR into the running JobManager container
docker cp src/flink_jobs/target/crypto-analyzer-flink-1.0.0.jar \
    flink-jobmanager:/opt/flink/

# Submit the job
docker exec flink-jobmanager \
    flink run -d /opt/flink/crypto-analyzer-flink-1.0.0.jar

# Or via Make:
make build-flink
make deploy-flink
```

### 5. Start the API and UIs

```bash
# In separate terminals:
make api           # FastAPI on :8000

# Next.js terminal:
cd frontend && npm install && npm run dev   # :3000
```

To run the Next.js terminal containerised instead of via `npm run dev`:

```bash
docker compose up -d --build frontend
```

> **Note:** if you've already initialised the Postgres volume on an older
> version of this project, the schema won't re-run automatically (new
> trade-level tables, continuous aggregates, expanded `cryptocurrencies`
> seed in `configs/init-db.sql`). Run `scripts/teardown.sh` once to drop
> the volume and re-initialise it.

### 6. Stop / teardown

```bash
bash scripts/stop_pipeline.sh    # stops producer + Flink job + docker-compose stop
bash scripts/teardown.sh         # removes all containers and volumes (destructive)
```

---

## Web Interfaces

| Service | URL | Role | Notes |
|---|---|---|---|
| **Next.js Terminal** | http://localhost:3000 | **Primary UI** | Public-facing market terminal — live ticker, global stats, market screener, per-coin detail, charts, alerts |
| FastAPI docs | http://localhost:8000/docs | Backend | Interactive Swagger UI |
| Flink Web UI | http://localhost:8082 | Backend | Job graph, checkpoints, metrics |
| Kafka UI | http://localhost:8081 | Backend | Topic browser, consumer groups |
| pgAdmin | http://localhost:5050 | Backend | PostgreSQL query tool |

PostgreSQL is exposed on host port **5433** (not 5432) to avoid conflicts with local installs.

---

## Frontend (Next.js Terminal)

The `frontend/` directory is the **primary user-facing platform**. It is a Next.js 16 App Router app built on React 19 + TypeScript, styled with Tailwind CSS v4, and uses Radix UI primitives.

### Stack

| Concern | Choice |
|---|---|
| Framework | Next.js 16 (App Router, Server Components, Server Actions) |
| Runtime | React 19 |
| Language | TypeScript (strict) |
| Styling | Tailwind CSS v4 + `tw-animate-css` |
| UI primitives | Radix UI (`@radix-ui/react-select`, `react-separator`, `react-slot`) + Shadcn-style wrappers |
| Charts | `lightweight-charts` v5 (TradingView) — candlestick + period switcher |
| Async state | `@tanstack/react-query` v5 (with devtools) |
| Schema validation | `zod` v4 — WS frames + REST responses are parsed through `zod` |
| Icons | `lucide-react` |
| Deployment | Multi-stage Node 20 Alpine Dockerfile (`frontend/Dockerfile`) |

### Routes

| Path | Type | Description |
|---|---|---|
| `/` | Server Component | Home dashboard: live ticker bar → global stats → BTC overview + trending → live section (symbol picker, stats, chart, alerts, candle table) → categories → paginated screener. |
| `/coins` | Server Component | Paginated market screener (10 coins/page) backed by CoinGecko proxy. Pagination uses `?page=N`. |
| `/coins/[id]` | Server Component | Per-coin detail page. Header + chart (CoinGecko OHLC + live WS overlay if backend-tracked) + exchange listings + converter + coin metadata + recent alerts (only for the 8 tracked symbols). |

### Data flow

The frontend pulls from two sources, in two different ways:

1. **CoinGecko REST** — used for the long tail of coins, global stats, trending, categories, and the rich historical OHLC used to seed charts. Calls go through `frontend/lib/coingecko.ts`, which is marked with `import "server-only"` so the API key is never bundled into the browser. Caching is delegated to Next.js ISR (`fetch(..., { next: { revalidate } })`):
   - `/global` → 60 s revalidate
   - `/coins/markets` (screener) → 60 s
   - `/coins/{id}` and `/coins/{id}/ohlc` → 60 s
   - `/search/trending` → 5 min
   - `/coins/categories` → 10 min
   - Client-triggered refetches (e.g. period switching on `CoinChart`) hop through a thin Server Action in `lib/coingecko-actions.ts`.

2. **Our FastAPI + WebSocket** — used for the 8 backend-tracked symbols. Calls go through `frontend/lib/api.ts` (`fetch` with Zod parsing) and `frontend/lib/ws.ts` (`useCryptoSocket`). On a coin detail page, if the CoinGecko slug matches one of our tracked symbols, the WS candle is merged into the chart's tail and the AlertsFeed is shown.

### `useCryptoSocket` hook (frontend/lib/ws.ts)

Subscribes to `ws://API/ws/prices/<symbol>` (or `ALL` for the ticker). Handles:

- Exponential-backoff reconnect: 1 s → 2 s → 4 s … capped at 30 s.
- 25 s ping interval; if no frame in 60 s the socket is force-closed and reconnected.
- Discriminated-union frames (`connection` / `initial_data` / `price_update` / `keepalive` / `pong`) are validated with Zod before being surfaced to React state. Bad frames are dropped silently.
- Returns `{ status, latestBySymbol }`; consumers read the latest candle per symbol off `latestBySymbol[sym]`.

### Component map

```
frontend/components/
├── Header.tsx                 Top navigation (logo + Home / All Coins)
├── LiveDashboardSection.tsx   Home page live block (symbol picker + chart + stats + alerts + candles)
├── DataTable.tsx              Generic table primitive used across CoinGecko tiles
├── cg/                        CoinGecko-sourced tiles (Server Components)
│   ├── GlobalStatsBar.tsx     Top-of-page market cap / volume / dominance strip
│   ├── CoinOverview.tsx       Bitcoin hero block on the home page
│   ├── TrendingTile.tsx       Top-7 trending coins by search volume
│   ├── CategoriesTile.tsx     Top-10 categories by market cap
│   ├── MarketScreener.tsx     Paginated market screener with sparklines
│   └── Sparkline.tsx          Inline 7-day sparklines (SVG)
├── coin/                      Coin-detail surface
│   ├── CoinHeader.tsx         Price + 24h/30d change badges
│   ├── CoinChart.tsx          lightweight-charts candlestick, period switcher, live merge
│   ├── LiveCoinDetail.tsx     Wires WS candles + AlertsFeed into the coin page
│   ├── ExchangeListings.tsx   Top 10 exchange tickers from CoinGecko
│   ├── Converter.tsx          Multi-currency price converter
│   └── CoinsPagination.tsx    Pagination for /coins
├── ticker/LiveTickerBar.tsx   WS-driven horizontal ticker (subscribes to ALL)
├── chart/SymbolPicker.tsx     Backend-tracked symbol selector
├── stats/StatsPanel.tsx       24h low/high/avg/volume tiles (FastAPI /historical/{sym}/stats)
├── ohlc/CandleTable.tsx       Recent 1-min Flink candles (FastAPI /historical/{sym})
├── alerts/AlertsFeed.tsx      PRICE_SPIKE / PRICE_DROP feed (FastAPI /alerts/{sym})
└── ui/                        Shadcn-style primitives (button, input, table, select, …)
```

### Frontend environment

`frontend/.env.local`:

| Variable | Purpose | Public? |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | FastAPI base URL — defaults to `http://localhost:8000` | Browser-exposed |
| `NEXT_PUBLIC_WS_URL` | WebSocket base URL — defaults to `ws://localhost:8000` | Browser-exposed |
| `COINGECKO_BASE_URL` | CoinGecko API base | Server-only |
| `COINGECKO_API_KEY` | Optional CoinGecko demo key (raises rate limits) | Server-only |

When you run the frontend in Docker via `docker compose up -d --build frontend`, the env block in `docker-compose.yml` injects the browser URLs at build time; you still need to set a `COINGECKO_API_KEY` if you want one, either via a build arg or by adding it to the compose `environment:` block.

---

## API Endpoints

```
GET  /health                              Service health (Redis + PostgreSQL)

GET  /api/v1/latest/all                   Latest OHLC for every supported symbol
GET  /api/v1/latest/{symbol}              Latest OHLC for one symbol

GET  /api/v1/historical/{symbol}          1-min candles, filterable by time range
GET  /api/v1/historical/{symbol}/stats    Min/max/avg/volume summary
GET  /api/v1/historical/{symbol}/latest   Most recent persisted candle

GET  /api/v1/alerts                       Recent anomaly alerts (all symbols)
GET  /api/v1/alerts/{symbol}              Alerts for one symbol

GET  /api/v1/symbols                      Tracked symbols (cryptocurrencies table)
GET  /api/v1/trending                     Top movers by 24h % change (candles_1h)

WS   /ws/prices/{symbol}                  Real-time stream via Redis Pub/Sub
                                          symbol ∈ tracked symbols | "ALL"
```

Symbols come from the `cryptocurrencies` table, read by the producer and API at startup and resolved by Flink inside its SQL. Add a symbol by inserting a row (with its `coinbase_product`) and restarting the producer and API.
The frontend never hard-codes the list — it reads `/api/v1/symbols` at runtime.

All responses include `X-Process-Time-Ms` (middleware) and `X-Request-ID` (UUID4, for tracing). `/api/v1/latest/*` is Redis-first with a TimescaleDB fallback on a cache miss, a corrupt cache entry, or a Redis outage; which one served the request is reported in the `X-Data-Source: redis|postgres` response header.

---

## Environment Variables

Copy `.env.example` to `.env`. Required variables:

| Variable | Default in example | Notes |
|---|---|---|
| `POSTGRES_PASSWORD` | `change_me_in_production` | **Must be set** |
| `PGADMIN_PASSWORD` | `change_me_in_production` | **Must be set** |
| `POSTGRES_USER` | `crypto_user` | |
| `POSTGRES_DB` | `crypto_db` | |
| `POSTGRES_HOST` | `localhost` | `postgres` when inside Docker network |
| `POSTGRES_PORT` | `5433` | Host-side port |
| `REDIS_HOST` | `localhost` | `redis` when inside Docker network |
| `REDIS_PORT` | `6379` | |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | `kafka:29092` inside Docker |
| `KAFKA_TRADES_TOPIC` | `crypto-trades` | Producer topic (older .env files may still say KAFKA_TOPIC; it is ignored) |
| `LOG_LEVEL` | `INFO` | |

Frontend-specific variables live in `frontend/.env.local` — see [Frontend environment](#frontend-environment).

---

## Make Targets

```bash
make setup-all      # Create venv and install all dependencies
make start          # docker-compose up (full mode)
make stop           # docker-compose down
make status         # Container status
make health         # Service health checks
make logs           # Flink TaskManager logs
make topics         # Create Kafka topics (idempotent)
make producer       # Run Python producer
make api            # Run FastAPI (uvicorn)
make test           # Run Python and Flink unit tests
make build-flink    # mvn clean package
make deploy-flink   # Copy the built JAR and submit (cancels a running job first); run `make build-flink` first
make stop-flink     # Cancel running Flink job
make clean          # Remove containers, volumes, build artifacts
```

The Next.js terminal is driven from `frontend/` using standard npm scripts (`npm run dev`, `npm run build`, `npm start`).

---

## Project Structure

```
.
├── configs/
│   ├── flink-conf.yaml                           # Flink cluster configuration
│   └── init-db.sql                               # TimescaleDB schema + retention policies
├── docs/                                         # Operational guides (testing, commands, troubleshooting)
├── scripts/
│   ├── start_pipeline.sh                         # Start everything with health checks
│   ├── stop_pipeline.sh                          # Graceful shutdown
│   ├── teardown.sh                               # Full cleanup (destructive)
│   └── wait_for_services.py                      # Health-check helper used by Makefile
├── src/
│   ├── api/                                      # FastAPI application
│   │   ├── database.py                           # asyncpg + redis.asyncio pools (lifespan)
│   │   ├── endpoints/                            # latest, historical, alerts, symbols, websocket
│   │   ├── middleware.py                         # Timing (perf_counter) + request tracing (UUID4)
│   │   └── main.py
│   ├── flink_jobs/                               # Java Maven project
│   │   └── src/main/java/com/crypto/analyzer/
│   │       ├── CryptoPriceAggregator.java        # Main job: dedup + OHLCV + anomaly detection + Kafka alert sink
│   │       ├── functions/
│   │       │   ├── CandleAggregator.java         # 1-min OHLCV + VWAP aggregation
│   │       │   ├── DedupByTradeId.java           # Keyed last-seen trade_id dedup
│   │       │   └── ZScoreAnomalyDetector.java    # EWMA z-score anomaly detector, State TTL
│   │       ├── models/
│   │       └── sinks/
│   │           └── JdbcSinks.java                # The three TimescaleDB sinks (raw_trades, candles, alerts)
│   └── producers/
│       └── coinbase_trades_producer.py           # Coinbase WebSocket trade producer
├── tests/                                        # Python unit tests (producers, API, symbols)
├── frontend/                                     # Next.js 16 terminal (primary UI)
│   ├── app/
│   │   ├── layout.tsx                            # Root layout + Geist fonts + Providers
│   │   ├── providers.tsx                         # QueryClientProvider (TanStack)
│   │   ├── page.tsx                              # Home dashboard (Server Component)
│   │   ├── globals.css                           # Tailwind v4 + design tokens
│   │   └── coins/
│   │       ├── page.tsx                          # /coins paginated screener
│   │       └── [id]/page.tsx                     # /coins/[id] detail
│   ├── components/                               # See "Component map" above
│   ├── lib/
│   │   ├── api.ts                                # FastAPI client (fetch + zod)
│   │   ├── ws.ts                                 # useCryptoSocket hook
│   │   ├── coingecko.ts                          # server-only CoinGecko proxy
│   │   ├── coingecko-actions.ts                  # Server Actions exposing the proxy to clients
│   │   ├── types.ts                              # Zod schemas for REST + WS payloads
│   │   ├── chart-config.ts                       # lightweight-charts theming + period config
│   │   ├── format.ts                             # USD / volume / cap / pct formatters
│   │   └── utils.ts                              # cn helper + small UI utilities
│   ├── public/                                   # Static assets (logo, converter icon, …)
│   ├── Dockerfile                                # Multi-stage Node 20 Alpine build
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── eslint.config.mjs
│   ├── postcss.config.mjs
│   └── package.json
├── docker-compose.yml                            # All services incl. `frontend`
├── requirements.txt                              # Producer + shared + test deps
└── requirements-api.txt                          # FastAPI, uvicorn, redis, pydantic-settings
```

---

## Docs

Detailed guides are in [`docs/`](docs/):

| File | Contents |
|---|---|
| `LOCAL_TESTING_GUIDE.md` | Setup walkthrough, common errors, resource requirements |
| `TROUBLESHOOTING.md` | PostgreSQL/TimescaleDB setup postmortem and fixes |
| `API_TESTING_GUIDE.md` | curl examples for every endpoint |
| `FLINK_COMMANDS.md` | Flink CLI reference for job management and savepoints |
| `DOCKER_COMMANDS.md` | Docker Compose cheat sheet |
| `DATABASE_CONNECTIONS.md` | Connection strings for psycopg2, JDBC, redis-py, pgAdmin |
| `REDIS_TESTING_GUIDE.md` | Verifying the Redis caching layer |
