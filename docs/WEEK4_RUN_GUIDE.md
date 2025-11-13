# Week 4 Implementation Guide - Step by Step

## 🎯 Complete Setup and Run Guide

Follow these steps exactly to get your data pipeline running!

---

## Pre-Flight Checklist

Before starting:
- [ ] Docker Desktop running
- [ ] All 8 containers up (`docker-compose ps`)
- [ ] Python 3.8+ installed (`python --version`)
- [ ] Git installed

---

## Step-by-Step Setup

### Step 1: Python Environment (5 minutes)

```powershell
# Navigate to project root
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate

# Verify activation (should see (venv) in prompt)
# Your prompt should now show: (venv) PS C:\Real-Time-Cryptocurrency-Market-Analyzer>

# Upgrade pip
python -m pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

# Verify kafka-python installed
pip show kafka-python
```

**Expected output:**
```
Name: kafka-python
Version: 2.0.2
Summary: Pure Python client for Apache Kafka
```

**Troubleshooting:**
- If `python` not found: Use `python3` or `py` instead
- If venv activation fails: Check Python installation
- If pip install fails: Run PowerShell as Administrator

---

### Step 2: Environment Configuration (2 minutes)

```powershell
# Copy environment template
copy .env.example .env

# (Optional) Edit if you changed default ports
notepad .env
```

**Default .env values work if:**
- ✅ Kafka on localhost:9092
- ✅ PostgreSQL on localhost:5433
- ✅ Redis on localhost:6379

**No changes needed if you followed Phase 2!** ✨

---

### Step 3: Verify Infrastructure (2 minutes)

```powershell
# Check all containers running
docker-compose ps

# Should see 8 containers all "Up":
# - kafka
# - zookeeper
# - kafka-ui
# - postgres
# - redis
# - pgadmin
# - flink-jobmanager
# - flink-taskmanager

# Test Kafka connection
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 | Select-Object -First 3

# Test PostgreSQL
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM cryptocurrencies;"
# Should return: 2 (BTC and ETH)

# Test Redis
docker exec redis redis-cli PING
# Should return: PONG
```

---

### Step 4: Create Kafka Topic (3 minutes)

**Option 1: Via Kafka UI (Recommended)**

1. Open browser: http://localhost:8081
2. Click **Topics** in left sidebar
3. Click **Add a Topic** button
4. Fill in:
   - **Name:** `crypto-prices`
   - **Number of Partitions:** `3`
   - **Replication Factor:** `1`
   - **Min In-Sync Replicas:** `1`
5. Click **Create Topic**
6. You should see `crypto-prices` in topics list

**Option 2: Via Command Line**

```powershell
docker exec kafka kafka-topics --create `
  --topic crypto-prices `
  --bootstrap-server localhost:9092 `
  --partitions 3 `
  --replication-factor 1

# Verify topic created
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
# Should include: crypto-prices
```

---

### Step 5: Run the Producer (5 minutes) 🚀

```powershell
# Make sure you're in project root with venv activated
cd C:\Real-Time-Cryptocurrency-Market-Analyzer
.\venv\Scripts\activate  # If not already activated

# Run producer
python src/producers/crypto_price_producer.py
```

**Expected Output:**
```
============================================================
Starting Cryptocurrency Price Producer
============================================================
Fetch interval: 10 seconds
Target cryptocurrencies: BTC, ETH
Kafka topic: crypto-prices
Will run indefinitely (Ctrl+C to stop)
2025-11-12 10:30:45 - INFO - Connected to Kafka at localhost:9092
2025-11-12 10:30:45 - INFO - Will produce to topic: crypto-prices

--- Iteration 1 ---
2025-11-12 10:30:46 - INFO - Produced: BTC $45,234.56 to partition 1 at offset 0
2025-11-12 10:30:46 - INFO - Produced: ETH $3,198.23 to partition 0 at offset 0
2025-11-12 10:30:46 - INFO - Iteration 1 completed in 1.23s
2025-11-12 10:30:46 - INFO - Total messages produced: 2, Errors: 0
2025-11-12 10:30:46 - INFO - Waiting 8.77s until next fetch...
```

**Let it run!** It will fetch prices every 10 seconds.

**What's happening:**
- CoinGecko API called every 10 seconds
- BTC and ETH prices fetched
- Messages sent to Kafka
- Partition assigned based on symbol hash

---

### Step 6: Verify in Kafka UI (2 minutes)

While producer is running:

1. **Open Kafka UI:** http://localhost:8081
2. **Click Topics** → `crypto-prices`
3. **Click Messages** tab
4. **You should see:**
   - Messages appearing in real-time
   - Both BTC and ETH messages
   - Incrementing offsets
   - JSON payload visible

**Click on a message** to expand and see full JSON!

---

### Step 7: Run the Consumer (5 minutes) 🎉

**Open a NEW PowerShell terminal** (keep producer running):

```powershell
# Navigate to project
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Activate venv
.\venv\Scripts\activate

# Run consumer
python src/consumers/simple_consumer.py
```

**Expected Output:**
```
============================================================
Starting Cryptocurrency Price Consumer
============================================================
Topic: crypto-prices
Press Ctrl+C to stop
============================================================
Connected to Kafka topic: crypto-prices

======================================================================
Message #1
======================================================================
Symbol:          BTC
Price:           $45,234.56
24h Volume:      $28,456,789,012
24h Change:      +2.34%
Timestamp:       2025-11-12T10:30:45.123456
Partition:       1
Offset:          0
======================================================================

======================================================================
Message #2
======================================================================
Symbol:          ETH
Price:           $3,198.23
24h Volume:      $15,234,567,890
24h Change:      -1.23%
Timestamp:       2025-11-12T10:30:45.234567
Partition:       0
Offset:          0
======================================================================
```

---

## ✅ Success Verification

You've succeeded if you have:

**Terminal 1 (Producer):**
```
Produced: BTC $X to partition 1 at offset Y
Produced: ETH $X to partition 0 at offset Y
```
(Running continuously)

**Terminal 2 (Consumer):**
```
Message #N
Symbol: BTC
Price: $X
```
(Showing each new message)

**Kafka UI:**
- Topic `crypto-prices` exists
- Message count increasing
- Consumer group `crypto-analyzer-group` visible
- Lag = 0 (real-time processing)

**Congratulations! Your streaming pipeline is LIVE!** 🎉

---

## 🧪 Optional: Test Filtering

Stop the consumer (Ctrl+C) and restart with filter:

```powershell
# Show only BTC prices
python src/consumers/simple_consumer.py --filter BTC

# You should ONLY see BTC messages now
# ETH messages are filtered out
```

---

## 🐛 Common Issues

### Issue 1: "ModuleNotFoundError: No module named 'kafka'"

**Cause:** Virtual environment not activated or dependencies not installed

**Fix:**
```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

### Issue 2: Producer can't connect to Kafka

**Error:** `NoBrokersAvailable: NoBrokersAvailable`

**Fix:**
```powershell
# Check Kafka running
docker-compose ps kafka
# Should show: Up

# Test connectivity
Test-NetConnection localhost -Port 9092

# If fails, restart Kafka
docker-compose restart kafka
```

---

### Issue 3: API rate limit errors

**Error:** `HTTP 429: Too Many Requests`

**Fix:**
Edit `src/config.py`:
```python
PRODUCER_FETCH_INTERVAL = 60  # Increase from 10 to 60 seconds
```

---

### Issue 4: Consumer shows no messages

**Possible causes:**

1. **Producer not running**
   - Check Terminal 1 - should see "Produced:" messages

2. **Wrong topic name**
   - Verify topic in Kafka UI matches `crypto-prices`

3. **Consumer started before producer**
   - Consumer reads from earliest, so should still get messages
   - Check `auto_offset_reset='earliest'` in config

**Debug:**
```powershell
# Check topic has messages
# Via Kafka UI → crypto-prices → Messages
# Should see message count > 0
```

---

## 📸 Screenshots for Portfolio

Take these screenshots:

1. **Producer terminal** - Showing multiple "Produced:" messages
2. **Consumer terminal** - Showing formatted price updates
3. **Kafka UI Messages** - crypto-prices topic with JSON payload visible
4. **Kafka UI Consumers** - crypto-analyzer-group with 0 lag
5. **Side-by-side terminals** - Producer and Consumer running simultaneously

---

## 🎓 What This Demonstrates

**For Interviews:**

✅ **Real-Time Data Ingestion**
- Fetching from external API
- Rate limiting and error handling
- Data validation

✅ **Kafka Producer Patterns**
- Keyed messages for partition affinity
- Durability configuration (acks='all')
- Serialization (JSON)

✅ **Kafka Consumer Patterns**
- Consumer groups
- Offset management
- Deserialization

✅ **End-to-End Pipeline**
- API → Kafka → Application
- Real-time data flow
- Observable at each stage

---

## ⏭️ Next Steps

After Week 4:
1. **Merge feature branch** to develop
2. **Tag release:** v0.2.0 - Phase 2 Complete
3. **Start Phase 3:** Flink streaming jobs
4. **Build:** Windowed aggregations, OHLC candles, write to PostgreSQL

---

**You now have a LIVE streaming data pipeline!** 🔥

Cryptocurrency prices flowing in real-time through your infrastructure! 💪

---

**Questions or issues? Check PHASE2_WEEK4.md for detailed documentation!**
