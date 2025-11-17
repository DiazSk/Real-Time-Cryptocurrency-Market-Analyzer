# Architecture Diagram - FAANG-Ready Version

## 🏗️ Complete System Architecture (With Failure Modes)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL DATA SOURCE                               │
│                                                                             │
│                    ┌──────────────────────────┐                            │
│                    │    CoinGecko API         │                            │
│                    │   (Public REST API)      │                            │
│                    └────────┬─────────────────┘                            │
│                             │                                               │
│                    Failure Mode: Rate limiting (50 req/min)                │
│                    Mitigation: Retry with exponential backoff              │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │ HTTP GET /simple/price
                              │ Poll interval: 30s
                              │ Serialization: JSON
                              ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION LAYER                                │
│                                                                             │
│              ┌────────────────────────────────────────┐                    │
│              │   Python Producer (crypto_price_producer.py)               │
│              │                                        │                    │
│              │   • Fetches BTC/ETH every 30s          │                    │
│              │   • Enriches: timestamp, volume        │                    │
│              │   • Serialization: JSON (not Avro)    │                    │
│              │   • Error handling: 3 retries, 5s backoff                  │
│              │                                        │                    │
│              │   Monitoring: Stdout logs only         │                    │
│              │   Scaling: Single instance (bottleneck at ~100 symbols)    │
│              └────────────┬───────────────────────────┘                    │
│                           │                                                 │
│                  Failure Mode: CoinGecko API down                          │
│                  Mitigation: Retry logic, graceful skip                    │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │ kafka-python-ng
                            │ Topic: crypto-prices (3 partitions)
                            │ Partitioning: Key-based (symbol) for ordering
                            │ Replication: factor=1 (DEV ONLY, should be 3 in PROD)
                            ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MESSAGE STREAMING LAYER                              │
│                                                                             │
│         ┌──────────────────────────────────────────┐                       │
│         │       Apache Kafka 7.5.0                 │                       │
│         │                                          │                       │
│         │  Topics:                                 │                       │
│         │  • crypto-prices (3 partitions)          │                       │
│         │  • crypto-alerts (1 partition)           │                       │
│         │                                          │                       │
│         │  Retention: 7 days / 1GB per partition   │                       │
│         │  Replication: 1 (DEV) / 3 (PROD)        │                       │
│         │                                          │                       │
│         │  Managed by: Zookeeper 7.5.0             │                       │
│         │  Persistence: Docker volumes (survives restarts)                │
│         └──────────────┬───────────────────────────┘                       │
│                        │                                                    │
│               Failure Mode: Broker crash                                   │
│               Mitigation: Kafka auto-recovery with persistent volumes      │
│                          Consumer offset tracking prevents data loss        │
└────────────────────────┼────────────────────────────────────────────────────┘
                         │ Flink Kafka Connector
                         │ Consumer Group: flink-crypto-analyzer
                         │ Offset strategy: Latest (not earliest)
                         │ Deserialize: JSON → PriceUpdate POJO
                         ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STREAM PROCESSING LAYER                               │
│                                                                             │
│         ┌──────────────────────────────────────────┐                       │
│         │   Apache Flink 1.18 (Java 21)            │                       │
│         │   JobManager (1) + TaskManager (1)       │                       │
│         │   Parallelism: 1 (single instance)       │                       │
│         │                                          │                       │
│         │   ┌────────────────────────────────┐     │                       │
│         │   │ CryptoPriceAggregator Job      │     │                       │
│         │   │                                │     │                       │
│         │   │ Event-time processing:         │     │                       │
│         │   │ • Watermarks: 10s out-of-order │     │                       │
│         │   │ • Tumbling windows: 1m, 5m, 15m│     │                       │
│         │   │                                │     │                       │
│         │   │ Operations:                    │     │                       │
│         │   │ • OHLC aggregation (custom)    │     │                       │
│         │   │ • Anomaly detection (stateful) │     │                       │
│         │   │ • Dual sink (parallel writes)  │     │                       │
│         │   │                                │     │                       │
│         │   │ State: RocksDB (disk-based)    │     │                       │
│         │   │ Checkpoints: Every 60s         │     │                       │
│         │   │ Semantics: Exactly-once        │     │                       │
│         │   └────────────────────────────────┘     │                       │
│         │                                          │                       │
│         │   Monitoring: Flink Web UI (http://localhost:8082)              │
│         │   Metrics: Records in/out, backpressure, checkpoint duration     │
│         └──────────────┬───────────────────────────┘                       │
│                        │                                                    │
│               Failure Mode: TaskManager crash                              │
│               Mitigation: Restart from last checkpoint (60s max data loss) │
│                          State persisted in RocksDB                        │
│                                                                             │
│               Scaling: Add TaskManagers, increase parallelism              │
│               Bottleneck: Currently single-threaded (parallelism=1)        │
└────────────────────────┼────────────────────────────────────────────────────┘
                         │ Triple Sink Pattern
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
   ┌─────────────┐ ┌──────────┐ ┌──────────────┐
   │   Redis     │ │PostgreSQL│ │ Kafka Topic  │
   │  (Cache)    │ │(Historical)  │(crypto-alerts)│
   └──────┬──────┘ └─────┬────┘ └──────┬───────┘
          │              │              │
          │ Jedis        │ JDBC         │ Kafka
          │ Connection   │ Connection   │ Producer
          │ Pool         │ Pool         │
          │ (10 conns)   │ (10 conns)   │
          │              │              │
┌─────────┼──────────────┼──────────────┼─────────────────────────────────────┐
│         │   STORAGE LAYER            │                                     │
│         │                            │                                     │
│    ┌────▼──────────┐          ┌──────▼────────────┐                       │
│    │  Redis 7      │          │  PostgreSQL 15    │                       │
│    │               │          │  + TimescaleDB    │                       │
│    │  Data Model:  │          │                   │                       │
│    │  String keys  │          │  Tables:          │                       │
│    │  JSON values  │          │  • price_aggregates_1m                    │
│    │               │          │    (hypertable, 1-day chunks)             │
│    │  Keys:        │          │  • price_alerts   │                       │
│    │  crypto:{SYM}:│          │  • cryptocurrencies│                       │
│    │   latest      │          │                   │                       │
│    │               │          │  Indexes:         │                       │
│    │  TTL: 45s     │          │  • (crypto_id, window_start)              │
│    │  (1.5x update)│          │    for range scans│                       │
│    │               │          │                   │                       │
│    │  Pub/Sub:     │          │  Retention: Unlimited                     │
│    │  Channel:     │          │  Backups: pg_dump nightly (if deployed)   │
│    │  crypto:updates          │                   │                       │
│    │  (PUBLISH on  │          │  UPSERT logic:    │                       │
│    │   cache write)│          │  ON CONFLICT (crypto_id, window_start)    │
│    │               │          │  DO UPDATE SET... │                       │
│    └────┬──────────┘          └──────┬────────────┘                       │
│         │                            │                                     │
│    Failure: Redis down               Failure: PostgreSQL down              │
│    Impact: Latest prices fail        Impact: Historical queries fail      │
│    Mitigation: API returns 503       Mitigation: API returns 503           │
│               Flink continues        Flink buffers (checkpoint state)      │
│               writing to PostgreSQL  writes resume on recovery             │
│                                                                             │
│    Scaling: Redis Cluster with      Scaling: Read replicas + connection   │
│             sharding by symbol      pooling (currently 10 conns max)       │
└─────────────┼──────────────────────┼──────────────────────────────────────┘
              │                      │
              │ Redis client         │ psycopg2
              │ GET/SUBSCRIBE        │ SQL queries
              ↓                      ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API LAYER                                        │
│                                                                             │
│              ┌────────────────────────────────────────┐                    │
│              │   FastAPI Backend (Python 3.11)        │                    │
│              │   Uvicorn ASGI server                  │                    │
│              │                                        │                    │
│              │   REST Endpoints:                      │                    │
│              │   • GET /api/v1/latest/{symbol}        │                    │
│              │     Cache: Redis, Latency: <10ms       │                    │
│              │   • GET /api/v1/historical/{symbol}    │                    │
│              │     Storage: PostgreSQL, Latency: <200ms                    │
│              │   • GET /api/v1/alerts/{symbol}        │                    │
│              │   • GET /health (Redis + PostgreSQL checks)                 │
│              │                                        │                    │
│              │   WebSocket:                           │                    │
│              │   • WS /ws/prices/{symbol}             │                    │
│              │   • Mode: Event-driven (Redis Pub/Sub) │                    │
│              │   • Latency: <100ms (measured)         │                    │
│              │   • Clients: Tested up to 25, can handle ~50               │
│              │                                        │                    │
│              │   Connection Pooling:                  │                    │
│              │   • Redis: 10 max connections          │                    │
│              │   • PostgreSQL: 10 max connections     │                    │
│              │                                        │                    │
│              │   Middleware:                          │                    │
│              │   • Performance logging (X-Request-ID) │                    │
│              │   • CORS (configured for localhost)    │                    │
│              └────────────┬───────────────────────────┘                    │
│                           │                                                 │
│                  Failure Mode: API instance crash                          │
│                  Mitigation: Manual restart (no load balancer in dev)      │
│                             Should use: Kubernetes with multiple replicas  │
│                                                                             │
│                  Scaling: Horizontal (add API instances behind LB)         │
│                  Bottleneck: Single instance, ~50 WebSocket clients max    │
└───────────────────────────┼─────────────────────────────────────────────────┘
                            │ HTTP REST / WebSocket
                            │ Port: 8000 (localhost only)
                            ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VISUALIZATION LAYER                                  │
│                                                                             │
│              ┌────────────────────────────────────────┐                    │
│              │   Streamlit Dashboard (Python)         │                    │
│              │   Port: 8501                           │                    │
│              │                                        │                    │
│              │   Components:                          │                    │
│              │   • Live price cards (Streamlit metrics)                    │
│              │   • Candlestick charts (Plotly)        │                    │
│              │   • Volume correlation (Plotly subplots)│                   │
│              │   • Moving averages (Pandas rolling)   │                    │
│              │   • Alert panel (Streamlit containers) │                    │
│              │                                        │                    │
│              │   Data fetching:                       │                    │
│              │   • Auto-refresh: 2s (Streamlit component)                  │
│              │   • HTTP client: requests library      │                    │
│              │   • Retry: 3 attempts with backoff     │                    │
│              │                                        │                    │
│              │   Rendering: Server-side (Streamlit),  │                    │
│              │             Client-side (Plotly JS)    │                    │
│              └────────────────────────────────────────┘                    │
│                                                                             │
│                  Failure Mode: API unavailable                             │
│                  Mitigation: Shows error message with recovery steps       │
│                             Graceful degradation (partial features work)   │
│                                                                             │
│                  Scaling: Streamlit Cloud (managed),                       │
│                          or Docker behind nginx                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow with Serialization Details

### 1. Ingestion (Every 30 seconds)
```
HTTP Response (JSON)
↓ Python dict
kafka-python Producer
↓ JSON.dumps() → bytes
Kafka (persistent log)
```

**Why JSON not Avro?**
- Simplicity for learning project
- Human-readable logs for debugging
- **Trade-off:** 3-5x larger messages, no schema evolution support

---

### 2. Stream Processing (Continuous)
```
Kafka Consumer
↓ JSON.parse() → Java POJO (PriceUpdate)
Flink Watermark Assignment (event-time from "timestamp" field)
↓ 10-second buffer for late arrivals
Tumbling Windows (1m, 5m, 15m)
↓ Aggregate function (OHLCAggregator)
Window Trigger
↓ Output: OHLCCandle POJO
Dual Sink
├─→ Redis: SETEX + PUBLISH (JSON string)
├─→ PostgreSQL: JDBC batch insert (100 records/batch or 5s interval)
└─→ Kafka: Alerts topic (JSON)
```

**Exactly-Once Guarantees:**
- Flink checkpoints every 60s
- Kafka transactions (idempotent producer)
- PostgreSQL UPSERT (ON CONFLICT)

---

### 3. API Serving (On-demand)
```
Client HTTP Request
↓ FastAPI routing
├─→ /latest → Jedis.get() → <1ms → JSON response
├─→ /historical → psycopg2.execute() → 50-200ms → JSON response  
└─→ /ws → Redis Pub/Sub listener → Async broadcast → <100ms push
```

**Connection Pooling:**
- Redis: JedisPool (10 max)
- PostgreSQL: SimpleConnectionPool (1-10 connections)

---

## 🚨 Failure Modes & Recovery

### Scenario 1: Redis Crashes
**Impact:**
- ❌ `/latest` endpoints return 503
- ❌ WebSocket stops receiving updates
- ✅ Flink continues writing to PostgreSQL
- ✅ Historical data queries still work

**Recovery:**
- Docker restart policy: `on-failure`
- Redis recovers in ~5 seconds
- Flink backfills cache with latest window

**Lesson:** Cache failures don't affect source of truth (PostgreSQL).

---

### Scenario 2: PostgreSQL Crashes
**Impact:**
- ❌ `/historical` endpoints return 503
- ❌ Flink JDBC sink fails, retries 3x
- ✅ `/latest` endpoints still work (Redis)
- ⚠️ Flink job may fail if retries exhausted

**Recovery:**
- Docker restart policy: `on-failure`
- PostgreSQL recovers from persistent volume
- Flink restarts from last checkpoint (max 60s data loss)

**Improvement Needed:** Circuit breaker to skip PostgreSQL sink if down.

---

### Scenario 3: Flink TaskManager Crashes
**Impact:**
- ⚠️ Processing stops for ~10-30 seconds
- ❌ No new OHLC windows during restart
- ✅ Kafka retains messages (7-day retention)

**Recovery:**
- Flink JobManager detects failure
- Restarts from last checkpoint (RocksDB state)
- Replays Kafka messages from checkpoint offset
- No data loss (exactly-once semantics)

**Current Limitation:** Single TaskManager (no HA).

---

### Scenario 4: CoinGecko API Rate Limit
**Impact:**
- ⚠️ Producer fails to fetch prices
- ❌ No new messages to Kafka

**Recovery:**
- Producer retry logic: 3 attempts with exponential backoff
- Skips failed fetch, continues next interval
- Logs error for monitoring

**Gap:** No dead letter queue, no alerting.

---

## 📈 Scalability Analysis

### Current Capacity
**Single Instance Limits:**
- Producer: ~2 symbols * 2 fetches/min = **4 requests/min to CoinGecko**
  - Limit: 50 req/min (CoinGecko free tier)
  - **Can scale to ~25 symbols** before hitting rate limit

- Flink (parallelism=1): **~20-30 msgs/sec** (measured: 0.1 msgs/sec actual)
  - Bottleneck: Single-threaded processing
  - **Can scale to ~1000 symbols** with parallelism=10

- API (single instance): **~50 WebSocket clients** (tested: 25)
  - Bottleneck: CPU for JSON serialization + broadcasting
  - **Can scale to 500+** with multiple instances behind load balancer

- Dashboard: **1 user** (Streamlit is single-session by default)
  - **Can scale to unlimited users** with Streamlit Cloud

### How to Scale 10x (to 20 symbols, 500 clients)

1. **Producer:**
   - No change needed (20 symbols = 40 req/min, under limit)

2. **Kafka:**
   - Increase partitions: 3 → 20 (one per symbol)
   - Add broker: 1 → 3 (replication factor=3)

3. **Flink:**
   - Increase parallelism: 1 → 10
   - Add TaskManagers: 1 → 5 (2 slots each)

4. **Redis:**
   - No change needed (write load is constant)

5. **PostgreSQL:**
   - Add read replica for query load
   - Connection pool: 10 → 50

6. **API:**
   - Deploy: 1 → 5 instances behind nginx load balancer
   - Sticky sessions for WebSocket (client → same API instance)

7. **Dashboard:**
   - Deploy to Streamlit Cloud (auto-scales)

**Estimated Cost (AWS):**
- Current (dev): $0/month (local Docker)
- 10x scale: ~$800/month (MSK, ECS, RDS, ElastiCache)

---

## 🎯 Data Serialization Trade-offs

### Current: JSON Everywhere
**Why:**
- Easy debugging (human-readable)
- No schema registry needed
- Python/Java interop is trivial

**Downsides:**
- 3-5x larger than Avro (~500 bytes vs ~150 bytes per message)
- No schema evolution support
- Slower serialization

### Alternative: Apache Avro
**Benefits:**
- Compact binary format
- Schema evolution (forward/backward compatibility)
- 60-70% size reduction

**Complexity:**
- Need Confluent Schema Registry
- More complex Java/Python setup
- Harder debugging

**Decision:** JSON is fine for 2 symbols, 6 msgs/min. At 1000 msgs/sec, switch to Avro.

---

## 🔍 Monitoring & Observability (MISSING - Future Work)

### What Should Be Added

**Metrics Collection:**
```
Flink → Prometheus (JMX exporter)
API → Prometheus (Python client)
Redis → Redis Exporter
PostgreSQL → Postgres Exporter
         ↓
    Prometheus Server
         ↓
    Grafana Dashboards
```

**Dashboards to Create:**
1. **Producer Health:** Success rate, API latency, messages/sec
2. **Flink Metrics:** Records in/out, backpressure, checkpoint duration
3. **API Performance:** Request rate, p50/p95/p99 latency, error rate
4. **Storage Health:** Redis hit rate, PostgreSQL query time, disk usage

**Alerting Rules:**
- Producer failure (no messages for 2 minutes)
- Flink job restart (checkpoint failure)
- API p99 latency >500ms
- Redis memory >80%
- PostgreSQL connection pool exhausted

---

## 🎓 Architecture Decisions Interview Questions

Be prepared to answer:

**Q: Why 3 Kafka partitions?**
**A:** Supports 3 parallel consumers for scalability. Chose 3 (not 1 or 10) because:
- More than symbols (2) for future growth
- Odd number helps with rebalancing
- 3 TaskManagers would utilize fully

**Q: Why 1-minute windows, not 5 seconds?**
**A:** Trade-off between granularity and statistical significance. 
- 5-second windows = 6 price samples (noisy, frequent spikes)
- 1-minute windows = 2 samples (more stable, fewer false alerts)
- Financial data typically uses 1-minute or 1-hour candles

**Q: Why persist Flink state to RocksDB, not in-memory?**
**A:** Recovery from crashes. In-memory state is lost on TaskManager failure. RocksDB persists to disk, survives restarts. Trade-off: Slower state access (disk I/O), but necessary for production.

**Q: Why single Flink JobManager (single point of failure)?**
**A:** Development simplicity. Production should use Flink HA with ZooKeeper or Kubernetes. Current SPOF is acceptable for learning project, unacceptable for production.

---

## 🎨 Creating the Visual Diagram

### Use Draw.io (30 minutes, NON-NEGOTIABLE)

**Required Elements:**
1. All components as boxes
2. Data flow arrows with labels (HTTP, Kafka, JDBC, Redis GET)
3. Failure mode annotations (red text boxes)
4. Latency annotations (e.g., "<10ms" near Redis)
5. Scaling notes (e.g., "Currently parallelism=1, can scale to 10")

**Color Coding:**
- Blue: External (CoinGecko)
- Green: Processing (Producer, Flink)
- Orange: Storage (Redis, PostgreSQL, Kafka)
- Purple: Serving (API, Dashboard)
- Red: Failure annotations

**Export as PNG:** 1920x1080 or higher, <2MB file size

**This diagram goes in your README and is shown in interviews.**

---

## ✅ Critical Path to v1.0.0

**Do ONLY this:**

1. **Create architecture diagram in Draw.io** (30 min)
   - Show failure modes
   - Show scaling paths
   - Save as: `docs/screenshots/architecture-diagram.png`

2. **Capture 3 screenshots** (15 min)
   - dashboard-candlestick-ma.png
   - dashboard-overview.png
   - architecture-diagram.png (export from Draw.io)

3. **Update README** (already done above - just add images)

4. **Git commit + merge + tag v1.0.0** (15 min)

**Total: 60 minutes to FAANG-ready**

---

**Status:** Ready to execute  
**Next:** Create Draw.io diagram with failure modes, commit, TAG v1.0.0