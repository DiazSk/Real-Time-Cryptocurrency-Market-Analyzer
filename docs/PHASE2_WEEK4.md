# Phase 2 - Week 4: Data Pipeline Implementation

## 🎯 Goal: Build end-to-end data pipeline with real cryptocurrency prices

**Time Budget:** 7-10 hours total (1-2 hours per day)

---

## 📋 What You're Building

This week connects everything together! You'll:
1. **Fetch real crypto prices** from CoinGecko API
2. **Stream them to Kafka** with proper partitioning
3. **Consume and validate** the data
4. **See prices flowing** through your entire infrastructure

**End Result:** Real BTC and ETH prices → Kafka → Console, ready for Flink processing!

---

## 📂 New Project Structure

```
src/
├── config.py                    # Central configuration
├── producers/
│   ├── __init__.py
│   └── crypto_price_producer.py  # CoinGecko → Kafka
├── consumers/
│   ├── __init__.py
│   └── simple_consumer.py         # Kafka → Console
└── utils/                         # Helper functions (future)
```

---

## Day 1-3: Cryptocurrency Price Producer

### 🎯 Objectives

1. ✅ Set up Python environment with dependencies
2. ✅ Create configuration management
3. ✅ Build CoinGecko API client
4. ✅ Implement Kafka producer
5. ✅ Test with real cryptocurrency prices

---

### Step 1: Python Environment Setup

```powershell
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
.\venv\Scripts\activate  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list | Select-String -Pattern "kafka"
# Should show: kafka-python 2.0.2
```

**Why Virtual Environment?**
- Isolates project dependencies
- Prevents version conflicts
- Easy to reproduce on other machines

---

### Step 2: Create Environment Variables

```powershell
# Copy the example file
copy .env.example .env

# Edit .env if needed (default values should work)
notepad .env
```

**Default values work out-of-the-box** if you've been following along! 🎉

---

### Step 3: Understand the Producer Code

Open `src/producers/crypto_price_producer.py` and review the key components:

#### **Class: CryptoPriceProducer**

**1. Initialization:**
- Sets up Kafka producer
- Loads cryptocurrency symbols from config
- Initializes counters

**2. fetch_crypto_prices():**
- Calls CoinGecko API
- Fetches: price, volume, market cap, 24h change
- Handles rate limiting and retries

**3. create_price_message():**
- Formats API response into structured JSON
- Adds metadata (timestamp, message_id)
- Prepares for Kafka

**4. produce_message():**
- Sends to Kafka topic
- Uses symbol as key (BTC/ETH → partition assignment)
- Logs partition and offset

**5. run():**
- Main loop
- Fetches prices every 10 seconds (configurable)
- Handles errors gracefully
- Ctrl+C for clean shutdown

---

### Step 4: Create Kafka Topic

Before running producer, create the topic:

```powershell
# Make sure infrastructure is running
docker-compose ps

# Open Kafka UI
start http://localhost:8081

# Create topic:
# - Name: crypto-prices
# - Partitions: 3
# - Replication Factor: 1
```

**Or via command line:**
```powershell
docker exec kafka kafka-topics --create `
  --topic crypto-prices `
  --bootstrap-server localhost:9092 `
  --partitions 3 `
  --replication-factor 1
```

---

### Step 5: Run the Producer! 🚀

```powershell
# Make sure you're in project root and venv is activated
cd C:\Real-Time-Cryptocurrency-Market-Analyzer
.\venv\Scripts\activate

# Run the producer
python src/producers/crypto_price_producer.py
```

**Expected Output:**
```
==========================================
Starting Cryptocurrency Price Producer
==========================================
Fetch interval: 10 seconds
Target cryptocurrencies: BTC, ETH
Kafka topic: crypto-prices
Will run indefinitely (Ctrl+C to stop)
Connected to Kafka at localhost:9092

--- Iteration 1 ---
Produced: BTC $45,234.56 to partition 1 at offset 0
Produced: ETH $3,198.23 to partition 0 at offset 0
Iteration 1 completed in 1.23s
Total messages produced: 2, Errors: 0
Waiting 8.77s until next fetch...
```

---

### Step 6: Verify in Kafka UI

While producer is running:

1. **Open Kafka UI:** http://localhost:8081
2. **Go to Topics** → `crypto-prices`
3. **Click Messages tab**
4. **You should see** live price updates appearing!

**Sample Message:**
```json
{
  "symbol": "BTC",
  "coin_id": "bitcoin",
  "price_usd": 45234.56,
  "volume_24h": 28456789012.34,
  "market_cap": 886543210987.65,
  "price_change_24h": 2.34,
  "last_updated": 1699876543,
  "timestamp": "2025-11-12T10:30:45.123456",
  "producer_id": "python-producer-v1",
  "message_id": "BTC-1699876545123"
}
```

**Key Observations:**
- **Key:** "BTC" or "ETH" (for partition assignment)
- **Value:** Complete price data as JSON
- **Partition:** Based on hash(key) % 3
- **Offset:** Incrementing for each message

---

### ✅ Day 1-3 Success Criteria

- [ ] Python environment set up with dependencies installed
- [ ] Created `crypto-prices` topic with 3 partitions
- [ ] Producer running and fetching prices every 10 seconds
- [ ] Messages visible in Kafka UI
- [ ] BTC and ETH prices both streaming
- [ ] No errors in producer logs
- [ ] Understand how keys determine partitions

---

## Day 4-7: Kafka Consumer with Filtering

### 🎯 Objectives

1. ✅ Build simple Kafka consumer
2. ✅ Read messages from topic
3. ✅ Print to console with formatting
4. ✅ Add filtering logic (optional: only BTC)
5. ✅ Verify end-to-end flow

---

### Step 1: Understand the Consumer Code

Open `src/consumers/simple_consumer.py` and review:

#### **Class: SimpleCryptoConsumer**

**1. Initialization:**
- Connects to Kafka
- Subscribes to crypto-prices topic
- Optional filtering by symbol

**2. process_message():**
- Parses JSON from Kafka
- Applies filter (if set)
- Formats and prints to console

**3. run():**
- Main consume loop
- Processes messages as they arrive
- Handles Ctrl+C gracefully

---

### Step 2: Run the Consumer

**Open a NEW terminal** (keep producer running in first terminal):

```powershell
# Navigate to project
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Activate virtual environment
.\venv\Scripts\activate

# Run consumer (all cryptocurrencies)
python src/consumers/simple_consumer.py

# OR run with filter (BTC only)
python src/consumers/simple_consumer.py --filter BTC
```

**Expected Output:**
```
========================================================================
Starting Cryptocurrency Price Consumer
========================================================================
Topic: crypto-prices
Press Ctrl+C to stop
========================================================================
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
```

---

### Step 3: Verify End-to-End Flow

You should now have:

**Terminal 1 (Producer):**
```
Produced: BTC $45,234.56 to partition 1 at offset 0
Produced: ETH $3,198.23 to partition 0 at offset 0
```

**Terminal 2 (Consumer):**
```
Message #1 - BTC $45,234.56
Message #2 - ETH $3,198.23
```

**Kafka UI:**
- Topic: crypto-prices
- Messages: Incrementing count
- Consumer Groups: crypto-analyzer-group (your consumer)

**This is your first end-to-end streaming data pipeline!** 🎉

---

### ✅ Day 4-7 Success Criteria

- [ ] Consumer running and receiving messages
- [ ] Messages printed to console with formatting
- [ ] Can filter by specific cryptocurrency (--filter BTC)
- [ ] Consumer group visible in Kafka UI
- [ ] Messages consumed from all 3 partitions
- [ ] No lag in consumer group (real-time processing)
- [ ] Clean shutdown with Ctrl+C works

---

## 🧪 Testing & Verification

### Test 1: Partition Assignment

Run producer and check which partition each crypto goes to:

**In Kafka UI → Messages:**
- Look at the Partition column
- BTC should always go to same partition
- ETH should always go to same partition
- Different symbols may go to different partitions

**Why?**
Kafka uses `hash(key) % num_partitions` for assignment.

---

### Test 2: Consumer Group Lag

**In Kafka UI → Consumers:**
- Find group: `crypto-analyzer-group`
- Check lag: Should be 0 or very low (<10)
- If lag growing: Consumer can't keep up with producer

---

### Test 3: Message Ordering

Within a partition, messages should be ordered:

```powershell
# Filter messages for BTC in Kafka UI
# Check offsets: 0, 1, 2, 3... (sequential)
# Check timestamps: Should be increasing
```

**Key Insight:** Ordering guaranteed within partition, not across partitions!

---

## 📸 Portfolio Screenshots

Capture these:

1. **Producer running** - Terminal showing "Produced: BTC..." messages
2. **Consumer running** - Terminal showing formatted price updates
3. **Kafka UI Messages** - crypto-prices topic with messages
4. **Kafka UI Consumers** - Consumer group with 0 lag
5. **Two terminals side-by-side** - Producer + Consumer simultaneously

---

## 🐛 Troubleshooting

### Issue: Producer can't connect to Kafka

```powershell
# Check Kafka is running
docker-compose ps kafka

# Check Kafka logs
docker-compose logs kafka | Select-String -Pattern "started"

# Verify port 9092 accessible
Test-NetConnection -ComputerName localhost -Port 9092
```

**Fix:** Make sure `KAFKA_BOOTSTRAP_SERVERS=localhost:9092` in config.py

---

### Issue: API rate limit exceeded

**Error:** `HTTP 429: Too Many Requests`

**Solution:**
- Increase `API_RATE_LIMIT_DELAY` in config.py to 60 seconds
- Or use `PRODUCER_FETCH_INTERVAL = 60` for slower fetching

**CoinGecko Free Tier:**
- 10-50 requests/minute
- With 2 cryptocurrencies, max 1 request per 6 seconds

---

### Issue: Consumer not receiving messages

```powershell
# Check consumer group exists
# In Kafka UI → Consumers
# Should see: crypto-analyzer-group

# Check topic has messages
# In Kafka UI → Topics → crypto-prices → Messages
```

**Fix:** Make sure producer ran successfully first!

---

### Issue: JSON parsing errors

**Error:** `JSONDecodeError: Expecting value`

**Cause:** Message value not valid JSON

**Debug:**
```python
# In consumer, add print before parsing:
print(f"Raw message: {message.value}")
# Check if it's valid JSON
```

---

## 🎓 Key Concepts Demonstrated

### Producer Concepts:

1. **Keyed Messages**
   - Key: Cryptocurrency symbol (BTC, ETH)
   - Value: Price data JSON
   - Key determines partition

2. **Serialization**
   - Python dict → JSON string → bytes
   - Kafka stores as bytes

3. **Acknowledgments (acks='all')**
   - Wait for message replication
   - Strongest durability guarantee
   - Trades latency for safety

4. **Retries**
   - Automatic retry on transient failures
   - Configured: 3 attempts
   - Prevents data loss

### Consumer Concepts:

1. **Consumer Groups**
   - Multiple consumers share load
   - Each partition assigned to one consumer
   - Automatic rebalancing on failure

2. **Offset Management**
   - Consumer tracks last read offset
   - Manual commit for exactly-once
   - Can replay from any offset

3. **Deserialization**
   - Bytes → JSON string → Python dict
   - Reverse of producer serialization

4. **At-Least-Once Delivery** (current setup)
   - Messages may be redelivered on consumer crash
   - Idempotent processing handles duplicates
   - Week 5-7: Upgrade to exactly-once with Flink

---

## 💡 Interview Talking Points

**Q: Walk me through your data pipeline.**

**Answer:**
> "I built a Python producer that fetches cryptocurrency prices from CoinGecko's public API every 10 seconds. The producer calls the /simple/price endpoint to get current prices, 24-hour volume, market cap, and price changes for Bitcoin and Ethereum.
>
> The data is formatted into JSON messages and sent to Kafka using partition-by-key—I use the cryptocurrency symbol (BTC or ETH) as the message key, which ensures all BTC updates go to the same partition, maintaining order for each coin. The producer is configured with acks='all' for durability and includes retry logic to handle transient API failures.
>
> On the consumption side, I have a simple consumer that reads from the crypto-prices topic and prints formatted price updates to the console. This demonstrates the basic streaming flow before adding Flink for complex processing. The consumer uses manual offset commits to enable exactly-once processing when I integrate with Flink in the next phase."

---

**Q: How do you handle API rate limits?**

**Answer:**
> "CoinGecko's free API tier allows 10-50 requests per minute. I handle this through configurable delays—currently 10 seconds between fetches, which gives me 6 requests/minute, safely under the limit. The producer includes exponential backoff retry logic that detects HTTP 429 (rate limit) responses and increases the wait time before retrying.
>
> I also batch the API call to fetch both BTC and ETH prices in a single request rather than separate calls, reducing API usage. For production or higher frequency needs, I could upgrade to CoinGecko's paid API tier or implement intelligent caching with Redis to reduce API dependencies."

---

**Q: Why use the cryptocurrency symbol as the message key?**

**Answer:**
> "Using the symbol as the key provides two critical benefits: ordering and partition affinity. Kafka guarantees message ordering within a partition, so by routing all BTC messages to the same partition, I ensure BTC price updates are processed in the order they arrived. This is essential for calculating accurate moving averages or detecting trends.
>
> The key also enables parallel processing—with 3 partitions, different Flink tasks can process BTC and ETH independently without coordination. In Week 5-7, when I add stateful Flink jobs, the keying ensures that all state for a given cryptocurrency stays on one task, avoiding distributed state management complexity."

---

## 📝 Code Walkthrough

### Producer Flow:

```python
1. Initialize Producer
   ↓
2. Connect to Kafka
   ↓
3. Main Loop:
   ├── Fetch prices from CoinGecko API
   ├── For each cryptocurrency:
   │   ├── Create message dict
   │   ├── Validate data
   │   └── Produce to Kafka (key=symbol)
   ├── Log statistics
   └── Sleep until next interval
   ↓
4. Cleanup (on Ctrl+C or error)
   ├── Flush remaining messages
   └── Close producer
```

### Key Configuration Parameters:

```python
# In config.py
PRODUCER_FETCH_INTERVAL = 10  # Fetch every 10 seconds
API_RATE_LIMIT_DELAY = 6      # Wait 6s between API calls
KAFKA_PRODUCER_CONFIG = {
    'acks': 'all',             # Wait for all replicas
    'retries': 3,              # Retry failures
    'compression_type': 'gzip' # Compress messages
}
```

---

## ⏭️ Next Steps After Week 4

After completing Day 1-7, you'll have:
- ✅ Real cryptocurrency prices streaming to Kafka
- ✅ Working producer and consumer
- ✅ End-to-end data flow verified

**Week 5-7 (Flink Jobs):**
- Build Flink streaming job in Java
- 1-minute windowed aggregations
- Calculate OHLC candles
- Write to PostgreSQL and Redis

---

## 🎯 Your Action Plan (Right Now!)

### Next 15 Minutes:
```powershell
# 1. Install dependencies
cd C:\Real-Time-Cryptocurrency-Market-Analyzer
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# 2. Copy environment file
copy .env.example .env

# 3. Verify Docker stack running
docker-compose ps
# All 8 containers should be "Up"
```

### Next 30 Minutes:
```powershell
# 4. Create Kafka topic
# Via Kafka UI: http://localhost:8081
# Name: crypto-prices
# Partitions: 3

# 5. Run producer
python src/producers/crypto_price_producer.py
# Should see: "Produced: BTC..." every 10 seconds
```

### Next 15 Minutes:
```powershell
# 6. Open new terminal, run consumer
cd C:\Real-Time-Cryptocurrency-Market-Analyzer
.\venv\Scripts\activate
python src/consumers/simple_consumer.py

# Should see formatted price updates!
```

---

## 💾 Commit Your Progress

```powershell
# Stage Week 4 files
git add src/ requirements.txt .env.example docs/PHASE2_WEEK4.md

# Commit
git commit -m "feat(pipeline): implement cryptocurrency price producer and consumer

Producer (Day 1-3):
- Created Python producer using CoinGecko API
- Fetches BTC and ETH prices every 10 seconds
- Produces to Kafka with symbol as key for partition affinity
- Configured acks='all' for durability
- Implements rate limiting (10 req/min) and retry logic
- Structured JSON messages with metadata

Consumer (Day 4-7):
- Created simple Kafka consumer with console output
- Reads from crypto-prices topic
- Formatted price display with partition/offset info
- Optional filtering by cryptocurrency symbol
- Manual offset commits for future exactly-once integration

Configuration:
- Central config.py for all settings
- Environment variable support via .env
- Validation on startup
- Feature flags for optional components

Dependencies:
- kafka-python for Kafka client
- requests for CoinGecko API
- psycopg2 and redis clients for future use
- Structured logging for production readiness

Verification:
- Tested with real BTC and ETH prices from CoinGecko
- Verified partition assignment by key
- Confirmed end-to-end flow: API → Kafka → Console
- Consumer group visible in Kafka UI with 0 lag

Completes Phase 2, Week 4, Day 1-7 objectives
Completes Phase 2 Infrastructure + Basic Pipeline"

# Push
git push origin feature/docker-setup
```

---

## 🎉 What You've Accomplished!

**Week 4 Complete means:**
- ✅ Real cryptocurrency prices flowing through Kafka
- ✅ Producer handling API rate limits correctly
- ✅ Consumer processing messages in real-time
- ✅ Partition affinity working (same key → same partition)
- ✅ Foundation ready for Flink aggregations

**Your streaming pipeline is ALIVE!** 🔥

Next up: Build Flink jobs to aggregate this data! 💪

---

**Run those commands now bhau and let me know once you see prices flowing!** 🚀
