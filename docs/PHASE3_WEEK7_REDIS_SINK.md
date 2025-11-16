# Phase 3 - Week 7 - Day 5-7: Redis Cache Sink ⚡

## 🎯 What We Built

**Production-grade Redis caching layer** for instant access to latest OHLC cryptocurrency data.

---

## 📦 Files Created/Updated

### **NEW Files:**

1. **`RedisSinkFunction.java`** - Custom Redis sink
   - Extends `RichSinkFunction<OHLCCandle>`
   - Uses Jedis connection pool
   - JSON serialization with Jackson
   - TTL: 5 minutes (300 seconds)
   - Thread-safe connection management

### **UPDATED Files:**

2. **`CryptoPriceAggregator.java`** - Added Redis sink
   - Dual-sink architecture (PostgreSQL + Redis)
   - 1-minute candles written to both sinks
   - Parallel writes (non-blocking)

3. **`WEEK7_REDIS_DEPLOY.bat`** - Deployment script
   - Tests Redis connectivity before deployment
   - Deploys job with both sinks

---

## 🏗️ Redis Cache Architecture

```
1-Min OHLC Stream
    ↓
    ├──→ PostgreSQL Sink (historical storage)
    └──→ Redis Sink (latest cache)

Redis Keys:
crypto:BTC:latest → {JSON with latest BTC candle}
crypto:ETH:latest → {JSON with latest ETH candle}

TTL: 300 seconds (auto-expire after 5 minutes)
```

---

## 🔑 Redis Key Pattern

**Key Structure:**
```
crypto:{SYMBOL}:latest
```

**Examples:**
- `crypto:BTC:latest` → Latest Bitcoin OHLC
- `crypto:ETH:latest` → Latest Ethereum OHLC

**Value:** JSON string
```json
{
  "symbol": "BTC",
  "windowStart": "2025-11-16T04:59:00Z",
  "windowEnd": "2025-11-16T05:00:00Z",
  "open": 95750.00,
  "high": 95750.00,
  "low": 95750.00,
  "close": 95750.00,
  "volumeSum": 78701577213.28,
  "eventCount": 2
}
```

**TTL:** 300 seconds (5 minutes)
- Auto-expires if no updates
- Prevents stale data

---

## 🔧 Redis Configuration

### **Connection Pool (Jedis):**
```java
Max Connections: 10
Max Idle: 5
Min Idle: 1
Connection Timeout: 2 seconds
Max Wait: 5 seconds
Test on Borrow: true (validate connections)
```

### **Why Connection Pool?**
- ✅ Thread-safe (multiple parallel tasks)
- ✅ Reuses connections (efficient)
- ✅ Auto-validates connections
- ✅ Handles connection failures gracefully

---

## 🚀 Build & Deploy

### **1. Deploy:**
```bash
cd C:\Real-Time-Cryptocurrency-Market-Analyzer
WEEK7_REDIS_DEPLOY.bat
```

### **2. Start Producer:**
```bash
START_PRODUCER.bat
```

### **3. Wait 2 minutes for windows**

---

## ✅ Verification

### **1. Check Redis Keys Exist:**

```bash
docker exec redis redis-cli KEYS "crypto:*"
```

**Expected:**
```
1) "crypto:BTC:latest"
2) "crypto:ETH:latest"
```

---

### **2. Get Latest BTC Candle:**

```bash
docker exec redis redis-cli GET crypto:BTC:latest
```

**Expected:** JSON string with OHLC data

---

### **3. Get Latest ETH Candle:**

```bash
docker exec redis redis-cli GET crypto:ETH:latest
```

**Expected:** JSON string with OHLC data

---

### **4. Check TTL:**

```bash
docker exec redis redis-cli TTL crypto:BTC:latest
```

**Expected:** Number between 1-300 (seconds remaining)

---

### **5. Verify Pretty JSON (using python):**

```bash
docker exec redis redis-cli GET crypto:BTC:latest | python -m json.tool
```

**Expected:**
```json
{
  "symbol": "BTC",
  "windowStart": "2025-11-16T05:10:00Z",
  "windowEnd": "2025-11-16T05:11:00Z",
  "open": 95750.00,
  ...
}
```

---

### **6. Verify PostgreSQL Still Working:**

```bash
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"
```

**Expected:** Count should still be increasing (both sinks working!)

---

## 🎓 Interview Talking Points

### **1. Dual-Sink Architecture**

> "I implemented a dual-sink pattern where 1-minute OHLC candles are written simultaneously to PostgreSQL for historical storage and Redis for low-latency access. This hybrid storage strategy optimizes for different access patterns—PostgreSQL handles complex time-range queries for analytics, while Redis provides sub-millisecond lookups for real-time dashboards and APIs."

### **2. Redis as Write-Through Cache**

> "The Redis sink operates as a write-through cache, updating the latest candle on every window close. With a 5-minute TTL, stale data automatically expires if the pipeline stops. This prevents serving outdated prices without requiring manual cache invalidation. The key pattern crypto:{symbol}:latest makes it simple to fetch current state with a single Redis GET command."

### **3. Connection Pooling with Jedis**

> "I used Jedis connection pooling to handle concurrent writes from multiple Flink parallel instances. The pool maintains 1-10 connections with health checking and automatic retry logic. This prevents connection exhaustion under load and gracefully handles Redis restarts without failing the Flink job."

### **4. Cache vs Database Trade-offs**

> "Redis serves as the speed layer for latest data access, while PostgreSQL is the system of record. If Redis goes down, the pipeline continues—only the cache is affected, not the permanent storage. This demonstrates understanding of fault isolation and appropriate technology selection for different access patterns."

---

## 🐛 Troubleshooting

### **Issue: No Redis keys appearing**

**Check:**
```bash
# 1. Redis container running?
docker ps | findstr redis

# 2. Redis accessible from Flink?
docker exec flink-taskmanager ping redis

# 3. Any Redis errors in logs?
docker logs flink-taskmanager | findstr "Redis"
```

**Solution:**
- Restart Redis: `docker-compose restart redis`
- Check Flink connectivity to redis:6379

---

### **Issue: Keys exist but no TTL**

**Check:**
```bash
docker exec redis redis-cli TTL crypto:BTC:latest
```

**If returns `-1`:** TTL not set (should be 1-300)

**Cause:** `setex()` not called correctly

**Solution:**
- Verify RedisSinkFunction uses `jedis.setex(key, ttlSeconds, json)`
- Not `jedis.set(key, json)` + `jedis.expire(key, ttl)` (two commands)

---

### **Issue: JSON parsing error when retrieving**

**Check:**
```bash
docker exec redis redis-cli GET crypto:BTC:latest
```

**If malformed JSON:**
- Check Jackson serialization in RedisSinkFunction
- Verify ObjectMapper has JavaTimeModule registered

---

## 📊 Performance Characteristics

**Write Performance:**
- Latency: <1ms per write (in-memory)
- Throughput: 2 writes/minute (BTC + ETH)
- Memory: ~2KB per key (JSON size)

**Read Performance:**
- Latency: <1ms (Redis GET)
- Throughput: Unlimited reads (cached data)
- No database load

**Comparison:**
| Operation | PostgreSQL | Redis |
|-----------|------------|-------|
| Write Latency | 5-50ms | <1ms |
| Read Latency | 10-100ms | <1ms |
| Range Queries | ✅ Fast | ❌ Not supported |
| Latest Value | ❌ Slow (SELECT MAX) | ✅ Instant (GET) |

---

## 🧪 Testing Commands Summary

```bash
# 1. Deploy
WEEK7_REDIS_DEPLOY.bat

# 2. Start producer
START_PRODUCER.bat

# 3. Wait 2 minutes

# 4. Check Redis keys
docker exec redis redis-cli KEYS "crypto:*"

# 5. Get BTC latest
docker exec redis redis-cli GET crypto:BTC:latest

# 6. Check TTL
docker exec redis redis-cli TTL crypto:BTC:latest

# 7. Verify PostgreSQL still working
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"
```

---

## ✅ Success Criteria

- [ ] Maven build succeeds
- [ ] Job name includes "PostgreSQL" or updated name
- [ ] Job RUNNING (not RESTARTING)
- [ ] Redis keys `crypto:BTC:latest` and `crypto:ETH:latest` exist
- [ ] Keys contain valid JSON
- [ ] TTL set to ~300 seconds
- [ ] PostgreSQL still receiving data
- [ ] No Redis connection errors in logs

---

## 🎯 What This Demonstrates

**For FAANG Interviews:**

1. ✅ **Polyglot storage** - SQL + NoSQL in one pipeline
2. ✅ **Cache patterns** - Write-through cache with TTL
3. ✅ **Connection pooling** - Thread-safe resource management
4. ✅ **Fault isolation** - Cache failure doesn't affect storage
5. ✅ **Custom sink implementation** - Not just using built-in connectors
6. ✅ **JSON serialization** - Proper Jackson configuration
7. ✅ **Production error handling** - Graceful degradation

---

**Status: ✅ Ready to deploy and test!**

*Created: November 16, 2025*  
*Branch: feature/redis-sink*  
*Completes: Phase 3, Week 7*
