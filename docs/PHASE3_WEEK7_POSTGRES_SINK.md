# Phase 3 - Week 7 - Day 1-4: PostgreSQL JDBC Sink 🗄️

## 🎯 What We Built

**Production-grade PostgreSQL sink for OHLC cryptocurrency data** with batch optimization and UPSERT logic.

---

## 📦 Files Created/Updated

### **NEW Files:**

1. **`CryptoIdMapper.java`** - Utility to map symbols → database IDs
   - BTC → crypto_id = 1
   - ETH → crypto_id = 2
   - Static mapping from database

2. **`OhlcDatabaseRecord.java`** - Database POJO
   - Matches `price_aggregates_1m` schema exactly
   - Auto-calculates `avg_price`: (O+H+L+C)/4
   - Factory method: `fromOhlcCandle()`
   - Validation logic

### **UPDATED Files:**

3. **`CryptoPriceAggregator.java`** - Added PostgreSQL sink
   - JDBC sink for 1-minute OHLC data
   - Batch inserts (100 records per batch)
   - UPSERT on conflict
   - Connection pooling

---

## 🏗️ PostgreSQL Sink Architecture

```
1-Min OHLC Stream
    ↓
Map to OhlcDatabaseRecord
    ↓
Filter (validate required fields)
    ↓
JDBC Sink (Batch of 100)
    ↓
PostgreSQL: price_aggregates_1m
```

---

## 🔧 Key Features

### **1. UPSERT Logic (ON CONFLICT)**

**SQL:**
```sql
INSERT INTO price_aggregates_1m (...) VALUES (...)
ON CONFLICT (crypto_id, window_start)
DO UPDATE SET
  open_price = EXCLUDED.open_price,
  high_price = EXCLUDED.high_price,
  ...
```

**Why:** Handles late-arriving data that re-triggers windows  
**Result:** Same window updated, not duplicated

---

### **2. Batch Optimization**

**Configuration:**
- **Batch size:** 100 records
- **Batch interval:** 5 seconds
- **Max retries:** 3

**Performance:**
- 100× fewer database connections
- Lower transaction overhead
- Better throughput

**Trade-off:**
- Slight latency (max 5 seconds)
- Acceptable for analytics use case

---

### **3. Data Mapping**

**OHLCCandle → OhlcDatabaseRecord:**

| Source Field | Database Column | Transformation |
|-------------|-----------------|----------------|
| symbol | crypto_id | BTC→1, ETH→2 (mapper) |
| windowStart | window_start | Instant → Timestamp |
| windowEnd | window_end | Instant → Timestamp |
| open | open_price | BigDecimal (direct) |
| high | high_price | BigDecimal (direct) |
| low | low_price | BigDecimal (direct) |
| close | close_price | BigDecimal (direct) |
| *calculated* | avg_price | (O+H+L+C)/4 |
| volumeSum | volume_sum | BigDecimal (direct) |
| eventCount | trade_count | Integer (direct) |

---

### **4. Connection Configuration**

**URL:** `jdbc:postgresql://postgres:5432/crypto_db`  
**Driver:** `org.postgresql.Driver`  
**User:** `crypto_user`  
**Password:** `crypto_pass`

**Connection Pooling:** Built into Flink JDBC connector  
**Retry Logic:** 3 attempts with exponential backoff

---

## 🚀 Build & Deploy

### **1. Build:**

```bash
cd C:\Real-Time-Cryptocurrency-Market-Analyzer\src\flink_jobs

mvn clean package
```

### **2. Stop old job:**

```bash
docker exec flink-jobmanager flink list
docker exec flink-jobmanager flink cancel <JOB_ID>
```

### **3. Deploy:**

```bash
cd ..\..
docker cp src\flink_jobs\target\crypto-analyzer-flink-1.0.0.jar flink-jobmanager:/opt/flink/

docker exec flink-jobmanager flink run -d /opt/flink/crypto-analyzer-flink-1.0.0.jar
```

### **4. Verify:**

```bash
docker exec flink-jobmanager flink list
# Expected: "Crypto Aggregator with PostgreSQL Sink (RUNNING)"
```

---

## ✅ Verification

### **1. Start Producer:**

```bash
START_PRODUCER.bat

# Let it run for 2-3 minutes to generate windows
```

---

### **2. Check Flink Output:**

```bash
docker logs -f flink-taskmanager

# Should see:
# 📊 [1-MIN] BTC OHLC | ...
# 📊 [1-MIN] ETH OHLC | ...
```

---

### **3. Query PostgreSQL (THE MOMENT OF TRUTH!):**

```bash
# Check row count
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"

# Should show increasing count as windows are processed
```

**View recent data:**

```bash
docker exec postgres psql -U crypto_user -d crypto_db -c "
SELECT 
    c.symbol,
    window_start,
    open_price,
    high_price,
    low_price,
    close_price,
    avg_price,
    volume_sum,
    trade_count
FROM price_aggregates_1m p
JOIN cryptocurrencies c ON p.crypto_id = c.id
ORDER BY window_start DESC
LIMIT 10;
"
```

**Expected output:**
```
 symbol |    window_start     | open_price | high_price | low_price | close_price |  avg_price  |   volume_sum    | trade_count
--------+---------------------+------------+------------+-----------+-------------+-------------+-----------------+-------------
 BTC    | 2025-11-16 01:20:00 | 95373.00   | 95373.00   | 95373.00  | 95373.00    | 95373.0000  | 105824979098.80 |           2
 ETH    | 2025-11-16 01:20:00 | 3153.50    | 3153.50    | 3153.50   | 3153.50     | 3153.5000   | 35987274225.49  |           2
```

---

### **4. Test Data Persistence:**

**Stop and restart Flink job:**

```bash
docker exec flink-jobmanager flink cancel <JOB_ID>
docker exec flink-jobmanager flink run -d /opt/flink/crypto-analyzer-flink-1.0.0.jar
```

**Query database again:**

```bash
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"
```

**Data should still be there!** ✅ (Persistent storage confirmed)

---

## 🎓 Interview Talking Points

### **1. UPSERT Strategy**

> "I implemented UPSERT using PostgreSQL's ON CONFLICT clause to handle late-arriving data that causes window re-triggering. Instead of creating duplicate rows, the database updates existing records with the latest OHLC values. This ensures data consistency while supporting Flink's exactly-once processing semantics."

### **2. Batch Optimization**

> "I configured the JDBC sink with batch size of 100 and 5-second intervals to optimize database throughput. This reduces connection overhead by 100× compared to individual inserts. The trade-off is a maximum 5-second delay in data visibility, which is acceptable for our analytics use case where sub-second latency isn't required."

### **3. Data Transformation**

> "The pipeline transforms streaming OHLCCandle objects into database-compatible records. This includes calculating the average price as (O+H+L+C)/4, mapping cryptocurrency symbols to foreign key IDs using a static mapper, and converting Java Instant timestamps to SQL Timestamps. The transformation is stateless and memory-efficient."

### **4. Error Handling & Retries**

> "The JDBC sink is configured with 3 retry attempts and exponential backoff. If a batch fails—for example, due to temporary database connection loss—Flink automatically retries before failing the job. Combined with checkpointing, this ensures no OHLC data is lost even during transient database issues."

---

## 🐛 Troubleshooting

### **Issue: No data in PostgreSQL after 5 minutes**

**Check:**
1. Flink job running?
   ```bash
   docker exec flink-jobmanager flink list
   ```

2. Producer sending data?
   ```bash
   # Should see Kafka messages
   docker logs flink-taskmanager | findstr "[1-MIN]"
   ```

3. Database connection working?
   ```bash
   docker exec flink-jobmanager flink list
   docker logs flink-taskmanager | findstr "SQLException"
   ```

---

### **Issue: Duplicate key constraint violation**

**Cause:** UPSERT not working, trying to INSERT duplicate windows

**Solution:**
- Verify SQL has `ON CONFLICT (crypto_id, window_start) DO UPDATE`
- Check constraint exists: `\d price_aggregates_1m` in psql

---

### **Issue: Build fails with "cannot find symbol: JdbcSink"**

**Cause:** Missing dependency

**Solution:**
```bash
# Verify pom.xml has:
# <artifactId>flink-connector-jdbc</artifactId>
# <version>3.1.2-1.18</version>

mvn clean install -U
```

---

## 📈 Performance Metrics

**Expected:**
- **Throughput:** 12-20 records/minute (2 symbols × 6 events/window)
- **Latency:** 70-75 seconds (60s window + 10s watermark + 5s batch)
- **Database writes:** ~0.2 TPS (transactions per second)
- **Batch efficiency:** 100 records per transaction

**With 100-record batching:**
- 100 OHLC candles = 1 database transaction
- At 2 candles/minute = 1 transaction every ~50 minutes
- Extremely efficient!

---

## ✅ Success Criteria

- [ ] Maven build succeeds
- [ ] Job submits without errors
- [ ] Job status: RUNNING (not RESTARTING)
- [ ] `price_aggregates_1m` row count increasing
- [ ] Data query shows recent OHLC candles
- [ ] BTC and ETH both writing
- [ ] No SQLException in logs
- [ ] UPSERT working (no duplicate key errors)

---

## ⏭️ What's Next

**After PostgreSQL sink verified:**
- Switch to `feature/redis-sink` branch
- Add Redis caching layer
- Cache latest prices for instant access
- Complete Week 7!

---

**Status: ✅ Ready to build and test!**

*Created: November 16, 2025*  
*Branch: feature/postgres-sink*  
*Next: Redis sink (Week 7, Day 5-7)*
