# Phase 2 - Week 3 - Day 5-7: Apache Flink Setup

## 🎯 Goal: Add stream processing engine to complete infrastructure

**Time Budget: 3-4 hours total**

---

## 📋 What You're Adding

### **Apache Flink**
Apache Flink is a distributed stream processing framework that will:
- Process cryptocurrency price streams in real-time
- Perform windowed aggregations (1-minute, 5-minute, etc.)
- Maintain stateful computations (moving averages, trends)
- Provide exactly-once processing guarantees
- Handle late-arriving data with watermarks

### **Components**

1. **JobManager (Port 8082)**
   - Coordinates stream processing jobs
   - Schedules tasks to TaskManagers
   - Manages checkpoints and savepoints
   - Provides Web UI for monitoring

2. **TaskManager**
   - Executes the actual stream processing
   - Runs parallel tasks (slots)
   - Maintains operator state
   - Handles data shuffling between operators

---

## 🏗️ Flink Architecture Overview

```
┌─────────────┐
│   Kafka     │ ─────► (Source)
│  (Prices)   │
└─────────────┘
                ┌──────────────────────┐
                │   Flink Cluster      │
                │                      │
                │  ┌────────────────┐  │
                │  │  JobManager    │  │ ◄── Coordinates
                │  └────────────────┘  │
                │          │           │
                │  ┌────────────────┐  │
                │  │  TaskManager   │  │ ◄── Executes
                │  │  (2 slots)     │  │
                │  └────────────────┘  │
                └──────────────────────┘
                         │
            ┌────────────┴────────────┐
            │                         │
    ┌───────▼───────┐         ┌──────▼──────┐
    │  PostgreSQL   │         │    Redis    │
    │ (Aggregates)  │         │  (Latest)   │
    └───────────────┘         └─────────────┘
```

---

## 🚀 Step 1: Update Docker Compose (Already Done!)

Your docker-compose.yml now includes:
- ✅ JobManager (Flink UI on port 8082)
- ✅ TaskManager (with 2 task slots)
- ✅ Shared Flink configuration
- ✅ Persistent volume for checkpoints/savepoints
- ✅ Connected to crypto-network

---

## 🔧 Step 2: Start Flink Services

```bash
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Stop existing services
docker-compose down

# Start everything (including Flink)
docker-compose up -d

# Wait 30 seconds for initialization
timeout /t 30

# Check status - should see 8 containers now!
docker-compose ps
```

**Expected Output:**
```
NAME                STATUS
kafka               Up
kafka-ui            Up
zookeeper           Up
postgres            Up (healthy)
redis               Up (healthy)
pgadmin             Up
flink-jobmanager    Up
flink-taskmanager   Up
```

---

## 🌐 Step 3: Access Flink Web UI

Open your browser and go to: **http://localhost:8082**

### **What You Should See:**

1. **Overview Tab** (default)
   - Task Managers: 1
   - Available Task Slots: 2
   - Running Jobs: 0
   - Completed Jobs: 0

2. **Task Managers Tab**
   - Shows your TaskManager container
   - CPU, memory, network stats
   - Number of available slots

3. **Job Manager Tab**
   - JobManager configuration
   - Logs and metrics

4. **Submit New Job Tab**
   - Upload JAR files
   - Configure job parameters
   - Submit streaming jobs

---

## 🧪 Step 4: Verify Flink Cluster

### **Check JobManager Logs**

```powershell
# View JobManager startup logs
docker-compose logs jobmanager | Select-String -Pattern "Started"

# Should see:
# "Started JobManager"
# "Web frontend listening at http://..."
```

### **Check TaskManager Connection**

```powershell
# View TaskManager logs
docker-compose logs taskmanager | Select-String -Pattern "Successful"

# Should see:
# "Successfully registered at the ResourceManager"
```

### **Verify Task Slots**

In Flink Web UI → **Task Managers**:
- Should show 1 TaskManager
- Available Slots: **2**
- Status: **Running**

---

## 🎯 Step 5: Understanding Flink Configuration

Open `configs/flink-conf.yaml` to see what we configured:

### **Key Settings for Cryptocurrency Processing:**

1. **Checkpointing (Fault Tolerance)**
   ```yaml
   execution.checkpointing.interval: 60000  # Every 60 seconds
   execution.checkpointing.mode: EXACTLY_ONCE
   ```
   - Ensures no data loss during failures
   - Exactly-once processing semantics

2. **State Backend (RocksDB)**
   ```yaml
   state.backend: rocksdb
   state.backend.incremental: true
   ```
   - Stores state on disk (handles large state)
   - Incremental checkpoints (faster)

3. **Parallelism**
   ```yaml
   parallelism.default: 2
   taskmanager.numberOfTaskSlots: 2
   ```
   - Can process 2 parallel streams
   - Scalable for multiple cryptocurrencies

4. **Restart Strategy**
   ```yaml
   restart-strategy: exponential-delay
   ```
   - Auto-restarts failed jobs
   - Exponential backoff prevents cascading failures

---

## 🎓 Understanding Stream Processing Concepts

### **1. Event Time vs Processing Time**

**Event Time** (what we'll use):
- When the price update actually happened
- Correct for out-of-order events
- Handles network delays properly

**Processing Time**:
- When Flink processes the event
- Simpler but less accurate
- Not suitable for financial data

### **2. Watermarks**

Watermarks tell Flink: *"All events before this timestamp have arrived"*

Example for crypto prices:
```
Current time: 10:00:30
Watermark: 10:00:20 (10 second delay)
Meaning: "All prices up to 10:00:20 have been received"
```

### **3. Windows**

**Tumbling Window** (no overlap):
```
[10:00:00 - 10:01:00] → Avg price: $45,000
[10:01:00 - 10:02:00] → Avg price: $45,100
[10:02:00 - 10:03:00] → Avg price: $45,050
```

**Sliding Window** (overlapping):
```
[10:00:00 - 10:01:00] → Avg: $45,000
[10:00:30 - 10:01:30] → Avg: $45,050
[10:01:00 - 10:02:00] → Avg: $45,100
```

### **4. Keyed State**

Store data per cryptocurrency:
```
BTC: { lastPrice: 45000, movingAvg: 44950, count: 1000 }
ETH: { lastPrice: 3200, movingAvg: 3180, count: 800 }
```

---

## 🧪 Step 6: Test Flink with Example Job (Optional)

Flink comes with example jobs. Let's test the cluster:

### **Option 1: Via Web UI**

1. Go to **Submit New Job** tab
2. You'll see pre-built examples in `/opt/flink/examples/streaming/`
3. Select `WordCount.jar`
4. Click **Submit**
5. Go to **Running Jobs** to see it execute

### **Option 2: Via Command Line**

```powershell
# Submit built-in example
docker exec flink-jobmanager flink run /opt/flink/examples/streaming/WordCount.jar

# Check job status
docker exec flink-jobmanager flink list

# View job output
docker-compose logs taskmanager
```

**What this proves:**
- ✅ JobManager can accept jobs
- ✅ TaskManager can execute jobs
- ✅ Cluster communication works
- ✅ Ready for custom crypto processing jobs

---

## 📊 Flink Metrics in Web UI

Explore the Web UI tabs:

### **Overview**
- Cluster health at a glance
- Number of running/completed jobs
- Resource utilization

### **Running Jobs**
- Real-time job execution
- Task distribution
- Checkpointing progress

### **Completed Jobs**
- Historical job runs
- Duration and throughput
- Failure reasons (if any)

### **Task Managers**
- CPU and memory usage
- Network I/O
- GC statistics
- Slot availability

---

## 🎓 Interview Talking Points

### **Why Apache Flink?**

> "I chose Apache Flink over alternatives like Spark Streaming or Kafka Streams because Flink provides true stream processing with low latency, exactly-once processing semantics, and sophisticated event-time handling. For financial data like cryptocurrency prices, Flink's watermark mechanism correctly handles out-of-order events caused by network delays, ensuring accurate aggregations."

### **Stateful Processing**

> "Flink's stateful processing allows me to maintain moving averages, detect trends, and track metrics per cryptocurrency without external databases. The state is checkpointed every 60 seconds for fault tolerance, meaning if a TaskManager fails, it restarts from the last checkpoint without data loss."

### **Parallelism and Scalability**

> "I configured 2 task slots per TaskManager, allowing parallel processing of multiple cryptocurrency streams. In production, I could scale horizontally by adding more TaskManagers to handle hundreds of coin pairs without changing the job code. The JobManager handles task distribution and load balancing automatically."

### **Exactly-Once Semantics**

> "Flink's exactly-once processing guarantees are critical for financial applications. By enabling checkpointing and using Kafka as source and PostgreSQL as sink, I ensure each price update is processed exactly once - never duplicated or lost - even during failures."

---

## 📸 Portfolio Screenshots

Capture these:
1. **docker-compose ps** - All 8 services running
2. **Flink Web UI Overview** - Showing cluster status
3. **Flink Task Managers** - Showing 2 available slots
4. **Flink Configuration** - The flink-conf.yaml settings

---

## ✅ Success Criteria

- [ ] JobManager container running
- [ ] TaskManager container running and connected
- [ ] Flink Web UI accessible at localhost:8082
- [ ] Task Managers showing 2 available slots
- [ ] Can submit example job successfully
- [ ] All 8 containers (Kafka, Postgres, Redis, pgAdmin, Flink x2, Zookeeper, Kafka UI) healthy

---

## 🐛 Troubleshooting

### **Problem: JobManager won't start**

```powershell
# Check logs
docker-compose logs jobmanager

# Common issues:
# - Port 8082 already in use (change in docker-compose.yml)
# - Memory limits too low (increase in flink-conf.yaml)
```

### **Problem: TaskManager can't connect to JobManager**

```powershell
# Check if they're on same network
docker network inspect real-time-cryptocurrency-market-analyzer_crypto-network

# Both should be listed
# Restart TaskManager
docker-compose restart taskmanager
```

### **Problem: Web UI not accessible**

```powershell
# Check JobManager is listening
docker exec flink-jobmanager netstat -tlnp | grep 8081

# Try accessing via container IP
docker inspect flink-jobmanager | Select-String -Pattern "IPAddress"
```

### **Problem: Out of Memory**

If containers crash with OOM:

```yaml
# In docker-compose.yml, increase memory limits:
jobmanager:
  environment:
    - |
      FLINK_PROPERTIES=
      jobmanager.memory.process.size: 2048m  # Increase from 1600m
```

---

## 🔄 Phase 2, Week 3 - COMPLETE!

After completing Day 5-7, you will have:

✅ **Week 3 Infrastructure Complete:**
- Day 1-2: Kafka + Zookeeper + Kafka UI ✅
- Day 3-4: PostgreSQL + TimescaleDB + Redis + pgAdmin ✅
- Day 5-7: Apache Flink (JobManager + TaskManager) ✅

**Full Stack:**
- Message Broker: Kafka
- Database: PostgreSQL with TimescaleDB
- Cache: Redis
- Stream Processing: Apache Flink
- Management UIs: Kafka UI, pgAdmin, Flink Web UI

**Ready for Week 4:** Building the actual data pipeline!

---

## ⏭️ Next Steps (Week 4)

**Day 1-3: Cryptocurrency Price Producer**
- Build Python producer
- Connect to CoinGecko API
- Produce price updates to Kafka
- Handle API rate limits

**Day 4-7: Consumer and Flink Processing**
- Build Kafka consumer
- Create Flink streaming job
- Windowed aggregations (1-min OHLC)
- Write to PostgreSQL and Redis

---

## 💾 Commit Your Work

```bash
# Stage changes
git add docker-compose.yml configs/flink-conf.yaml PHASE2_DAY5-7.md

# Commit
git commit -m "feat(flink): add Apache Flink for stream processing

- Added Flink JobManager (orchestrator) on port 8082
- Added Flink TaskManager with 2 task slots
- Configured RocksDB state backend for stateful processing
- Enabled checkpointing (60s interval) for fault tolerance
- Configured exactly-once processing semantics
- Set up exponential backoff restart strategy
- Created shared Flink volume for checkpoints/savepoints
- Integrated with Kafka and PostgreSQL for end-to-end pipeline
- Added comprehensive Flink configuration with production settings

Configuration Highlights:
- Parallelism: 2 (scalable for multiple cryptocurrencies)
- State Backend: RocksDB (incremental checkpoints)
- Checkpointing: 60 seconds, exactly-once mode
- Restart Strategy: Exponential delay with backoff
- Memory: 1600MB JobManager, 1728MB TaskManager

Completes Phase 2, Week 3, Day 5-7 objectives
Completes Phase 2 Infrastructure Setup (Weeks 3-4)"

# Push
git push origin feature/docker-setup
```

---

**Time to add stream processing power to your infrastructure, bhau!** 💪

Run `docker-compose down && docker-compose up -d` and access **http://localhost:8082** to see Flink! 🚀
