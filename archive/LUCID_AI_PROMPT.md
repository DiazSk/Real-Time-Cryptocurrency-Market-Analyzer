# Lucid AI Prompt for Architecture Diagram

## 🎯 How to Use This Prompt

1. Go to [Lucidchart](https://lucid.app)
2. Create a new document
3. Click on "Lucid AI" or "Generate with AI"
4. Copy and paste the prompt below
5. Review and adjust the generated diagram
6. Export as PNG (1920x1080 or higher)

---

## 📋 Copy This Exact Prompt to Lucid AI

```
Create a detailed technical architecture diagram for a real-time cryptocurrency market analyzer system with the following layers and components flowing top-to-bottom:

LAYER 1 - EXTERNAL DATA SOURCE (Top, Light Blue #E3F2FD):
- Package/Container labeled "EXTERNAL DATA SOURCE"
- Inside: Rectangle box "CoinGecko API (Public REST API)"
- Add red note box on right: "Failure Mode: Rate limiting (50 req/min), Mitigation: Retry with exponential backoff"
- Arrow down labeled "HTTP GET /simple/price\nPoll interval: 30s\nSerialization: JSON"

LAYER 2 - DATA INGESTION LAYER (Light Green #E8F5E9):
- Package/Container labeled "DATA INGESTION LAYER"
- Inside: Rectangle "Python Producer (crypto_price_producer.py)" with bullet points:
  • Fetches BTC/ETH every 30s
  • Enriches: timestamp, volume
  • Serialization: JSON (not Avro)
  • Error handling: 3 retries, 5s backoff
  • Monitoring: Stdout logs only
  • Scaling: Single instance (bottleneck at ~100 symbols)
- Add red note box on right: "Failure Mode: CoinGecko API down, Mitigation: Retry logic, graceful skip"
- Arrow down labeled "kafka-python-ng\nTopic: crypto-prices (3 partitions)\nPartitioning: Key-based (symbol)\nReplication: factor=1 (DEV)"

LAYER 3 - MESSAGE STREAMING LAYER (Light Orange #FFF3E0):
- Package/Container labeled "MESSAGE STREAMING LAYER"
- Inside: Rectangle "Apache Kafka 7.5.0" with:
  Topics:
  • crypto-prices (3 partitions)
  • crypto-alerts (1 partition)
  
  Retention: 7 days / 1GB per partition
  Replication: 1 (DEV) / 3 (PROD)
  Managed by: Zookeeper 7.5.0
  Persistence: Docker volumes
- Add red note box on right: "Failure Mode: Broker crash, Mitigation: Auto-recovery with persistent volumes, Consumer offset tracking prevents data loss"
- Arrow down labeled "Flink Kafka Connector\nConsumer Group: flink-crypto-analyzer\nOffset strategy: Latest\nDeserialize: JSON → PriceUpdate POJO"

LAYER 4 - STREAM PROCESSING LAYER (Light Green #E8F5E9):
- Package/Container labeled "STREAM PROCESSING LAYER"
- Inside: Rectangle "Apache Flink 1.18 (Java 21)\nJobManager (1) + TaskManager (1)\nParallelism: 1"
- Nested inner box: "CryptoPriceAggregator Job" with:
  Event-time processing:
  • Watermarks: 10s out-of-order
  • Tumbling windows: 1m, 5m, 15m
  
  Operations:
  • OHLC aggregation (custom)
  • Anomaly detection (stateful)
  • Triple sink (parallel writes)
  
  State: RocksDB (disk-based)
  Checkpoints: Every 60s
  Semantics: Exactly-once
  
  Monitoring: Flink Web UI (localhost:8082)
- Add red note box on right: "Failure Mode: TaskManager crash, Mitigation: Restart from last checkpoint (60s max data loss), State persisted in RocksDB, Scaling: Add TaskManagers, increase parallelism, Bottleneck: Currently parallelism=1"
- Three arrows down labeled "Triple Sink Pattern" pointing to three different storage boxes

LAYER 5 - STORAGE LAYER (Light Orange #FFF3E0):
- Package/Container labeled "STORAGE LAYER"
- Three boxes side by side:

Left box - "Redis 7 (Cache)":
  Data Model:
  • String keys
  • JSON values
  
  Keys: crypto:{SYM}:latest
  TTL: 45s (1.5x update)
  
  Pub/Sub:
  • Channel: crypto:updates
  • PUBLISH on cache write
  
  Connection: Jedis Pool (10 conns)
- Arrow from Flink labeled "Jedis Connection Pool\n(10 conns)\nSETEX + PUBLISH\nLatency: <10ms"
- Red note below: "Failure: Redis down, Impact: Latest prices fail (503), Mitigation: Flink continues to PostgreSQL, Scaling: Redis Cluster with sharding"

Middle box - "PostgreSQL 15 + TimescaleDB (Historical Storage)":
  Tables:
  • price_aggregates_1m (hypertable, 1-day chunks)
  • price_alerts
  • cryptocurrencies
  
  Indexes:
  • (crypto_id, window_start) for range scans
  
  Retention: Unlimited
  UPSERT: ON CONFLICT
  Connection: JDBC Pool (10 conns)
- Arrow from Flink labeled "JDBC Connection Pool\n(10 conns)\nBatch insert (100 records/5s)\nLatency: <50ms"
- Red note below: "Failure: PostgreSQL down, Impact: Historical queries fail (503), Mitigation: Flink buffers, retries, Scaling: Read replicas + connection pooling"

Right box - "Kafka Topic (crypto-alerts)":
  Alert messages from Flink
  Kafka Producer
- Arrow from Flink labeled "Kafka Producer\nTopic: crypto-alerts\nFormat: JSON"

LAYER 6 - API LAYER (Light Purple #F3E5F5):
- Package/Container labeled "API LAYER"
- Inside: Rectangle "FastAPI Backend (Python 3.11, Uvicorn ASGI)" with:
  REST Endpoints:
  • GET /api/v1/latest/{symbol}
    Cache: Redis, Latency: <10ms
  • GET /api/v1/historical/{symbol}
    Storage: PostgreSQL, Latency: <200ms
  • GET /api/v1/alerts/{symbol}
  • GET /health (Redis + PostgreSQL checks)
  
  WebSocket:
  • WS /ws/prices/{symbol}
  • Mode: Event-driven (Redis Pub/Sub)
  • Latency: <100ms (measured)
  • Clients: Tested 25, can handle ~50
  
  Connection Pooling:
  • Redis: 10 max connections
  • PostgreSQL: 10 max connections
  
  Middleware:
  • Performance logging (X-Request-ID)
  • CORS (configured for localhost)
- Arrows from Redis labeled "Redis client\nGET/SUBSCRIBE\nLatency: <10ms"
- Arrows from PostgreSQL labeled "psycopg2\nSQL queries\nLatency: 50-200ms"
- Add red note box on right: "Failure Mode: API instance crash, Mitigation: Manual restart (no LB in dev), Should use: Kubernetes with replicas, Scaling: Horizontal (add instances behind LB), Bottleneck: ~50 WebSocket clients max"
- Arrow down labeled "HTTP REST / WebSocket\nPort: 8000\nProtocol: HTTP/1.1, WS"

LAYER 7 - VISUALIZATION LAYER (Light Purple #F3E5F5):
- Package/Container labeled "VISUALIZATION LAYER"
- Inside: Rectangle "Streamlit Dashboard (Python)\nPort: 8501" with:
  Components:
  • Live price cards (Streamlit metrics)
  • Candlestick charts (Plotly)
  • Volume correlation (Plotly subplots)
  • Moving averages (Pandas rolling)
  • Alert panel (Streamlit containers)
  
  Data fetching:
  • Auto-refresh: 2s (Streamlit component)
  • HTTP client: requests library
  • Retry: 3 attempts with backoff
  
  Rendering:
  • Server-side (Streamlit)
  • Client-side (Plotly JS)
- Add red note box on right: "Failure Mode: API unavailable, Mitigation: Error message with recovery steps, Graceful degradation, Scaling: Streamlit Cloud (managed) or Docker behind nginx"

ADDITIONAL ANNOTATIONS:
- Add a note box at the top showing "Data Flow: 1. CoinGecko API → Producer (30s polling), 2. Producer → Kafka (3 partitions), 3. Kafka → Flink (event-time processing), 4. Flink → Triple Sink (Redis/PostgreSQL/Kafka), 5. API → Dashboard (REST/WebSocket)"
- Add a note box at the bottom showing "Key Metrics: Producer: 4 req/min (can scale to 25 symbols), Flink: Parallelism=1 (can scale to 10), API: 50 WebSocket clients (can scale to 500+), Latency: <10ms (Redis), <100ms (WebSocket), <200ms (PostgreSQL), Exactly-Once Semantics: Flink checkpoints every 60s, Kafka transactions (idempotent producer), PostgreSQL UPSERT (ON CONFLICT)"

STYLING REQUIREMENTS:
- Use background colors: #E3F2FD (Blue) for External, #E8F5E9 (Green) for Processing, #FFF3E0 (Orange) for Storage, #F3E5F5 (Purple) for API/UI
- Use #FFCDD2 (Light Red) background with #D32F2F (Dark Red) border for all failure mode notes
- Make all layer headers bold and centered
- Use solid black arrows with labels for primary data flow
- Include latency metrics on all arrows where applicable (<10ms, <50ms, <100ms, <200ms)
- Show connection pool sizes clearly (10 conns)
- Make the triple sink pattern visually distinct with three separate arrows from Flink

LEGEND (Top-right corner):
Create a legend box with:
- Light Blue (#E3F2FD) = External Sources
- Light Green (#E8F5E9) = Data Processing
- Light Orange (#FFF3E0) = Storage Systems
- Light Purple (#F3E5F5) = API/UI Layer
- Light Red (#FFCDD2) = Failure Modes (Notes)
```

---

## 🎨 Manual Adjustments After AI Generation

After Lucid AI generates the base diagram, make these refinements:

### 1. **Add Color Coding**
- Select External layer → Fill: Light Blue (#E3F2FD)
- Select Processing layers → Fill: Light Green (#E8F5E9)
- Select Storage boxes → Fill: Light Orange (#FFF3E0)
- Select API/Dashboard → Fill: Light Purple (#F3E5F5)

### 2. **Add Failure Annotations (Red Text Boxes)**
- Font color: Red (#D32F2F)
- Add small text boxes near each component
- Example: "⚠️ Failure: Redis down → /latest returns 503"

### 3. **Add Metrics Labels**
- Near arrows, add small labels with latency
- Use consistent format: "<10ms", "~50-200ms"
- Add throughput where relevant: "~4 req/min", "parallelism=1"

### 4. **Add Scaling Notes**
- Small callout boxes with dotted borders
- Example near Flink: "🔧 Scale: parallelism 1→10, add TaskManagers"
- Example near API: "🔧 Scale: 1→5 instances behind nginx"

### 5. **Format Arrows**
- Use different arrow styles:
  - Solid arrows for primary data flow
  - Dashed arrows for monitoring/metrics
  - Dotted arrows for failure scenarios
- Label every arrow with protocol (HTTP, Kafka, JDBC, Redis GET)

### 6. **Add Connection Details**
- Small labels on arrows from Flink to storage:
  - "Jedis Pool (10 conns)"
  - "JDBC Pool (10 conns)"
  - "Kafka Producer"

### 7. **Layer Headers**
- Add bold, centered text above each layer:
  - "EXTERNAL DATA SOURCE"
  - "DATA INGESTION LAYER"
  - "MESSAGE STREAMING LAYER"
  - "STREAM PROCESSING LAYER"
  - "STORAGE LAYER"
  - "API LAYER"
  - "VISUALIZATION LAYER"

### 8. **Add Legend**
- Create a separate box in top-right corner
- Title: "Color Legend"
- Show color samples with labels

---

## 🔄 Alternative: Iterate with Lucid AI

If the first generation isn't perfect, use these follow-up prompts:

### Prompt 2 (Add More Detail):
```
Enhance the diagram by adding:
- Failure mode annotations in red text next to each component
- Latency labels on arrows (<10ms for Redis, <100ms for WebSocket, <200ms for PostgreSQL)
- Connection pool sizes (10 connections each for Redis and PostgreSQL)
- Scaling notes showing current capacity and scale targets
- A legend showing color coding: Blue=External, Green=Processing, Orange=Storage, Purple=Serving
```

### Prompt 3 (Fix Layout):
```
Reorganize the diagram to:
- Flow strictly top-to-bottom
- Align boxes horizontally within each layer
- Make the Storage layer show three boxes side-by-side (Redis, PostgreSQL, Kafka)
- Ensure all arrows have clear labels
- Add bold section headers for each layer
```

### Prompt 4 (Add Technical Details):
```
Add these technical specifications:
- Kafka: "3 partitions, replication factor=1, 7-day retention"
- Flink: "Exactly-once semantics, RocksDB state, 60s checkpoints"
- PostgreSQL: "TimescaleDB hypertables, 1-day chunks"
- Redis: "TTL 45s, Pub/Sub enabled"
- Producer: "30s polling interval, 3 retries, exponential backoff"
```

---

## 📸 Export Settings

Once you're happy with the diagram:

1. **File → Export → PNG**
2. **Settings:**
   - Resolution: 300 DPI (high quality)
   - Size: Custom (1920 x 1080 or larger)
   - Background: White
   - Include: Everything
3. **Save as:** `architecture-diagram.png`
4. **Move to:** `c:\Real-Time-Cryptocurrency-Market-Analyzer\docs\screenshots\`

---

## ✅ Quality Checklist

Before finalizing, verify:

- [ ] All 7 layers are clearly visible
- [ ] All components have labels and details
- [ ] Every arrow has a protocol/format label
- [ ] Failure modes are annotated in red
- [ ] Latency metrics are shown (<10ms, <100ms, <200ms)
- [ ] Scaling notes are present (parallelism, instances)
- [ ] Color coding matches legend
- [ ] Connection pool sizes are shown (10 conns)
- [ ] Export is high-resolution (1920x1080+)
- [ ] File size is reasonable (<5MB)

---

## 🎯 Expected Output

Your final diagram should show:

1. **Clear data flow** from CoinGecko → Producer → Kafka → Flink → Storage → API → Dashboard
2. **Triple sink pattern** from Flink to Redis/PostgreSQL/Kafka alerts
3. **Failure scenarios** with mitigation strategies
4. **Performance metrics** (latencies, throughput, capacity)
5. **Scaling paths** (current vs target parallelism/instances)
6. **Connection details** (pools, protocols, ports)

---

## 🚀 Time Estimate

- Initial AI generation: **2-3 minutes**
- Manual refinements: **15-20 minutes**
- Export and save: **2 minutes**

**Total: ~20-25 minutes for a FAANG-ready architecture diagram**

---

**Next Steps:**
1. Copy the main prompt above
2. Go to Lucidchart and use Lucid AI
3. Make manual adjustments per section
4. Export as PNG
5. Save to `docs/screenshots/architecture-diagram.png`
6. Update README.md with the image

**You'll have a professional architecture diagram that explains:**
- What each component does
- How they communicate
- What happens when things fail
- How to scale the system

**This is THE diagram you'll show in interviews!** 🎯
