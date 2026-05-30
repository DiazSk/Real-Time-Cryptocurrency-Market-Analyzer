# Real-Time Cryptocurrency Market Analyzer

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A streaming data pipeline that ingests live cryptocurrency prices from the CoinGecko API, aggregates them into OHLC candlesticks using Apache Flink, and serves the results through a FastAPI backend, a **Next.js 16 web terminal** (primary UI), and a Streamlit ops dashboard (interim / internal use).

Tracks **8 symbols** end-to-end: `BTC`, `ETH`, `SOL`, `XRP`, `ADA`, `DOGE`, `AVAX`, `MATIC`. Runs entirely in Docker.

---

## Architecture

![Architecture diagram](docs/screenshots/architecture-diagram-high-level.png)
<!-- ```
CoinGecko API
     │
     ▼
Python Producer  (tenacity retry + exponential backoff)
     │
     ▼  Kafka topic: crypto-prices
     │
     ▼
Apache Flink  (Java, event-time, tumbling windows)
 ├─ 1-min OHLC  ──► PostgreSQL / TimescaleDB  (UPSERT)
 ├─ 1-min OHLC  ──► Redis  (latest candle, 300s TTL)
 ├─ 5-min OHLC  ──► stdout
 ├─ 15-min OHLC ──► stdout
 └─ Anomaly Detector  ──► Kafka topic: crypto-alerts
                               │
                               ▼
                          FastAPI alerts endpoint
     │
     ▼
FastAPI  (asyncpg + redis.asyncio, no blocking I/O)
 ├─ GET /api/v1/latest/{symbol}     ← Redis
 ├─ GET /api/v1/historical/{symbol} ← PostgreSQL
 ├─ GET /api/v1/alerts              ← PostgreSQL
 ├─ GET /api/v1/symbols             ← static (config)
 ├─ GET /api/v1/trending            ← PostgreSQL (v_latest_prices view)
 └─ WS  /ws/prices/{symbol}        ← Redis Pub/Sub
     │
     ├──► Next.js Terminal    (primary UI,    :3000)
     │      ├─ Server Components → CoinGecko REST proxy (ISR-cached)
     │      └─ Client Components → useCryptoSocket / TanStack Query
     │
     └──► Streamlit Dashboard (interim ops view, :8501)
``` -->

### Key implementation details

| Concern | Implementation |
|---|---|
| Retry / backoff | `tenacity` `@retry` with `wait_random_exponential`, replaces hand-rolled sleep loops |
| Flink checkpointing | Chandy-Lamport snapshots every 60 s, `EXACTLY_ONCE`, retained on cancellation |
| Flink state TTL | `AnomalyDetector` state expires after 1 h to prevent unbounded RocksDB growth |
| Kafka alert sink | `DeliveryGuarantee.EXACTLY_ONCE` (Flink-Kafka transactional integration) |
| PostgreSQL sink | At-least-once + idempotent `ON CONFLICT DO UPDATE` (same visible result) |
| Async API drivers | `asyncpg` + `redis.asyncio`; connection pools stored on `app.state` via lifespan |
| TimescaleDB retention | Native `add_retention_policy` — 7 days for raw data, 90 days for aggregates |
| Next.js data fetching | Server Components + `fetch` ISR for CoinGecko; TanStack Query for backend REST; `useCryptoSocket` for WS |
| Frontend WS resilience | Exponential-backoff reconnect (1 s → 30 s), 25 s ping, 60 s dead-frame timeout, Zod-validated frames |
| Streamlit refresh | `st_autorefresh` (non-blocking); `time.sleep + st.rerun` was removed |

---

## Prerequisites

- Docker Desktop with Compose (≥ v2)
- Python 3.11+
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
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt \
            -r requirements-api.txt \
            -r requirements-dashboard.txt
```

### 3. Start the pipeline

```bash
bash scripts/start_pipeline.sh
```

This script: checks dependencies → loads `.env` → runs `docker-compose up -d` → waits for Kafka, PostgreSQL, and Redis to be healthy → starts the producer in the background.

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

# Primary UI — Next.js 16 terminal:
cd frontend && npm install && npm run dev   # :3000

# Interim ops dashboard — Streamlit:
make dashboard     # :8501
```

To run the Next.js terminal containerised instead of via `npm run dev`:

```bash
docker compose up -d --build frontend
```

> **Note:** if you've already initialised the Postgres volume on an older
> version of this project (BTC/ETH only), the expanded `cryptocurrencies`
> seed in `configs/init-db.sql` won't re-run. Either insert the new symbols
> by hand or run `scripts/teardown.sh` to drop the volume and re-init.

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
| Streamlit Dashboard | http://localhost:8501 | Interim / ops | Internal ops view — quick charts, alerts, CSV export |
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

GET  /api/v1/symbols                      Supported symbols + display metadata
GET  /api/v1/trending                     Top movers by 24h % change

WS   /ws/prices/{symbol}                  Real-time stream via Redis Pub/Sub
                                          symbol ∈ SUPPORTED_SYMBOLS | "ALL"
```

The supported-symbol allowlist lives in `src/api/config.py::SUPPORTED_SYMBOLS`
and must stay in sync with `src/config.py::CRYPTO_IDS` (producer),
`configs/init-db.sql` (DB seed), and
`src/flink_jobs/.../CryptoIdMapper.java` (Flink crypto_id map).
The frontend never hard-codes the list — it reads `/api/v1/symbols` at runtime.

All responses include `X-Process-Time-Ms` (middleware) and `X-Request-ID` (UUID4, for tracing).

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
| `COINGECKO_API_KEY` | _(unset)_ | Optional; increases CoinGecko rate limits |
| `LOG_LEVEL` | `INFO` | |

Frontend-specific variables live in `frontend/.env.local` — see [Frontend environment](#frontend-environment).

---

## Make Targets

```bash
make setup-all      # Create venv and install all dependencies
make start          # docker-compose up (full mode)
make stop           # docker-compose stop
make status         # Container status
make health         # Service health checks
make logs           # Flink TaskManager logs
make producer       # Run Python producer
make api            # Run FastAPI (uvicorn)
make dashboard      # Run Streamlit (interim ops view)
make build-flink    # mvn clean package
make deploy-flink   # Build + submit Flink job
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
│   ├── consumers/                                # (Reserved for future consumers)
│   ├── dashboard/                                # Streamlit application (interim ops view)
│   ├── flink_jobs/                               # Java Maven project
│   │   └── src/main/java/com/crypto/analyzer/
│   │       ├── CryptoPriceAggregator.java        # Main job: OHLC + sinks + checkpointing
│   │       ├── functions/
│   │       │   ├── AnomalyDetector.java          # KeyedProcessFunction, State TTL
│   │       │   ├── OHLCAggregator.java
│   │       │   └── OHLCWindowFunction.java
│   │       ├── models/
│   │       ├── sinks/
│   │       │   └── RedisSinkFunction.java
│   │       └── utils/CryptoIdMapper.java         # Symbol → CoinGecko id map (8 symbols)
│   └── producers/
│       └── crypto_price_producer.py              # tenacity retry, Kafka producer
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
├── requirements.txt                              # Core + tenacity
├── requirements-api.txt                          # FastAPI, asyncpg, redis
└── requirements-dashboard.txt                    # Streamlit, plotly, streamlit-autorefresh
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
