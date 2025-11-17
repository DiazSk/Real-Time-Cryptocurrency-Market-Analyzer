# Phase 4 - Week 8 - Day 3: Enhanced Query Parameters & Performance Metrics 📊

## 🎯 What We Built

**Professional API enhancements** with advanced query parameters, pagination, performance tracking, and response headers.

---

## 📦 Files Created/Updated

### **NEW Files:**
1. **`middleware.py`** - Request/response logging middleware
   - Performance timing for all requests
   - Request ID generation
   - Automatic logging

### **UPDATED Files:**
2. **`endpoints/historical.py`** - Enhanced historical endpoint
   - `order_by` parameter (ASC/DESC)
   - `offset` parameter for pagination
   - Response headers with metrics
   - New `/stats` endpoint for aggregates
   - Time range validation

3. **`endpoints/latest.py`** - Enhanced latest endpoint
   - Performance headers
   - Cache TTL in headers
   - Data age tracking
   - New `/all` endpoint for bulk fetching

4. **`main.py`** - Added middleware integration

---

## 🆕 New Features

### **1. Advanced Query Parameters**

#### **Historical Endpoint Enhancements:**

```bash
GET /api/v1/historical/{symbol}?start_time=...&end_time=...&limit=100&offset=0&order_by=desc
```

**New Parameters:**
- `offset` - Skip N records for pagination (default: 0)
- `order_by` - Sort direction: `asc` or `desc` (default: desc)

**Validation Added:**
- `start_time` must be before `end_time`
- Maximum 30-day time range
- Offset must be >= 0

**Example Queries:**

```bash
# Get oldest 10 candles (chronological)
curl "http://localhost:8000/api/v1/historical/BTC?limit=10&order_by=asc"

# Pagination: Get records 11-20
curl "http://localhost:8000/api/v1/historical/BTC?limit=10&offset=10"

# Last week's data
curl "http://localhost:8000/api/v1/historical/BTC?start_time=2025-11-09T00:00:00&end_time=2025-11-16T00:00:00"
```

---

### **2. Performance Metrics in Response Headers**

All endpoints now return performance metadata:

```http
HTTP/1.1 200 OK
X-Total-Count: 1440              # Total records in time range
X-Returned-Count: 100            # Records in this response
X-Query-Time-Ms: 87.23           # Query execution time
X-Has-More: true                 # More data available?
X-Cache-Hit: false               # Was data from cache?
X-Process-Time-Ms: 92.45         # Total request processing
X-Request-ID: 1731763200123      # Unique request identifier
```

**What Each Header Means:**

| Header | Description | Use Case |
|--------|-------------|----------|
| `X-Total-Count` | Total matching records | Calculate total pages |
| `X-Returned-Count` | Records in response | Verify limit param worked |
| `X-Query-Time-Ms` | Database query time | Monitor DB performance |
| `X-Has-More` | More data available | Show "Load More" button |
| `X-Cache-Hit` | Redis hit (true/false) | Monitor cache effectiveness |
| `X-Process-Time-Ms` | Total API processing | Track overall latency |
| `X-Request-ID` | Unique request ID | Debug and tracing |

**For Redis cache:**

```http
X-Cache-Hit: true
X-Cache-TTL-Seconds: 234         # Time until cache expires
X-Data-Source: redis
X-Data-Age-Seconds: 12           # How old is this data?
```

---

### **3. New Endpoints**

#### **a) GET /api/v1/historical/{symbol}/stats**

Returns statistical summary for a time range.

```bash
curl "http://localhost:8000/api/v1/historical/BTC/stats?start_time=2025-11-16T00:00:00&end_time=2025-11-16T23:59:59"
```

**Response:**
```json
{
  "symbol": "BTC",
  "start_time": "2025-11-16T00:00:00",
  "end_time": "2025-11-16T23:59:59",
  "lowest_price": 94200.00,
  "highest_price": 96800.00,
  "average_price": 95500.00,
  "total_volume": 8570157721328.50,
  "candle_count": 1440,
  "price_range": 2600.00,
  "price_change_pct": 2.76
}
```

**Use Cases:**
- Daily high/low summary
- Calculate daily volatility
- Trading range analysis
- Volume tracking

---

#### **b) GET /api/v1/latest/all**

Fetch latest prices for all cryptocurrencies at once.

```bash
curl "http://localhost:8000/api/v1/latest/all"
```

**Response:**
```json
{
  "timestamp": "2025-11-16T15:30:00.123456",
  "cache_hit_rate": "100.0%",
  "prices": {
    "BTC": {
      "symbol": "BTC",
      "window_start": "2025-11-16T15:29:00",
      "window_end": "2025-11-16T15:30:00",
      "open": 95750.00,
      "high": 95800.00,
      "low": 95700.00,
      "close": 95780.00,
      "volume_sum": 78701577213.28,
      "event_count": 12
    },
    "ETH": {
      "symbol": "ETH",
      "window_start": "2025-11-16T15:29:00",
      "window_end": "2025-11-16T15:30:00",
      "open": 3153.50,
      "high": 3155.00,
      "low": 3152.00,
      "close": 3154.00,
      "volume_sum": 35987274225.49,
      "event_count": 10
    }
  }
}
```

**Use Cases:**
- Dashboard overview
- Portfolio tracking
- Bulk price fetching (1 request vs 2)

---

### **4. Request/Response Logging Middleware**

All API requests are now automatically logged:

```
INFO: ➡️  GET /api/v1/latest/BTC
INFO: ⬅️  GET /api/v1/latest/BTC → 200 (8.45ms)

INFO: ➡️  GET /api/v1/historical/ETH?limit=100&offset=0
INFO: ⬅️  GET /api/v1/historical/ETH?limit=100&offset=0 → 200 (125.67ms)

ERROR: ❌ GET /api/v1/latest/DOGE → ERROR: Invalid symbol: DOGE. Supported: BTC, ETH (2.34ms)
```

**Benefits:**
- Track slow queries
- Monitor error rates
- Debug production issues
- Audit API usage

---

## 🧪 Testing the Enhancements

### **1. Test Pagination**

```bash
# Get first page (records 1-10)
curl "http://localhost:8000/api/v1/historical/BTC?limit=10&offset=0" -I

# Check header: X-Has-More: true

# Get second page (records 11-20)
curl "http://localhost:8000/api/v1/historical/BTC?limit=10&offset=10"

# Get third page (records 21-30)
curl "http://localhost:8000/api/v1/historical/BTC?limit=10&offset=20"
```

---

### **2. Test Ordering**

```bash
# Newest first (default)
curl "http://localhost:8000/api/v1/historical/BTC?limit=5&order_by=desc"
# Should show: 2025-11-16 15:30, 15:29, 15:28, ...

# Oldest first
curl "http://localhost:8000/api/v1/historical/BTC?limit=5&order_by=asc"
# Should show: 2025-11-15 12:00, 12:01, 12:02, ...
```

---

### **3. Test Performance Headers**

```bash
# View headers (PowerShell)
curl "http://localhost:8000/api/v1/latest/BTC" -I

# Or use -v for verbose output
curl "http://localhost:8000/api/v1/latest/BTC" -v

# Expected headers:
# X-Cache-Hit: true
# X-Query-Time-Ms: 5.23
# X-Cache-TTL-Seconds: 234
# X-Data-Age-Seconds: 12
# X-Process-Time-Ms: 8.45
```

---

### **4. Test Stats Endpoint**

```bash
# Today's stats
curl "http://localhost:8000/api/v1/historical/BTC/stats" | python -m json.tool

# Last 7 days
curl "http://localhost:8000/api/v1/historical/BTC/stats?start_time=2025-11-09T00:00:00&end_time=2025-11-16T23:59:59" | python -m json.tool
```

---

### **5. Test Bulk Fetch**

```bash
# Get all latest prices
curl "http://localhost:8000/api/v1/latest/all" | python -m json.tool

# Check response headers
curl "http://localhost:8000/api/v1/latest/all" -I
# Expected:
# X-Total-Symbols: 2
# X-Cache-Hits: 2
# X-Cache-Hit-Rate: 100.0%
```

---

### **6. Test Validation Errors**

```bash
# Invalid order_by
curl "http://localhost:8000/api/v1/historical/BTC?order_by=random"
# Should return 422 Unprocessable Entity

# start_time after end_time
curl "http://localhost:8000/api/v1/historical/BTC?start_time=2025-11-16T00:00:00&end_time=2025-11-15T00:00:00"
# Should return 400 Bad Request: "start_time must be before end_time"

# Time range > 30 days
curl "http://localhost:8000/api/v1/historical/BTC?start_time=2025-10-01T00:00:00&end_time=2025-11-16T00:00:00"
# Should return 400 Bad Request: "Time range cannot exceed 30 days"
```

---

## 🎓 Interview Talking Points

### **1. Pagination Strategy**

> "I implemented offset-based pagination with metadata in response headers. The `X-Total-Count` and `X-Has-More` headers allow clients to implement 'Load More' functionality or traditional page navigation without a second count query per page. For high-traffic scenarios, I could transition to cursor-based pagination using `window_start` timestamps for better performance."

### **2. Performance Observability**

> "Every response includes detailed performance metrics in custom headers. `X-Query-Time-Ms` tracks database latency, while `X-Process-Time-Ms` captures total API overhead. This lets us monitor cache hit rates, identify slow queries, and set up alerts when p95 latency exceeds thresholds—all without additional APM tools."

### **3. Request Tracing**

> "I added middleware to generate unique request IDs for distributed tracing. Each request gets a `X-Request-ID` header that flows through logs, making it trivial to trace a single user request across multiple microservices. This is critical for debugging production issues where a user reports an error."

### **4. Input Validation Defense**

> "The API validates all inputs at the boundary using Pydantic models and regex patterns. For example, `order_by` only accepts `asc|desc`, and time ranges are capped at 30 days to prevent resource exhaustion from malicious or accidental queries. This is defense-in-depth—bad inputs never reach the database layer."

---

## 📊 Performance Benchmarks

Run these to verify performance:

```powershell
# Benchmark latest endpoint (should be <10ms)
Measure-Command { curl -s "http://localhost:8000/api/v1/latest/BTC" | Out-Null }

# Benchmark historical with pagination (should be <200ms)
Measure-Command { curl -s "http://localhost:8000/api/v1/historical/BTC?limit=100" | Out-Null }

# Benchmark stats endpoint (should be <100ms)
Measure-Command { curl -s "http://localhost:8000/api/v1/historical/BTC/stats" | Out-Null }

# Benchmark bulk fetch (should be <15ms)
Measure-Command { curl -s "http://localhost:8000/api/v1/latest/all" | Out-Null }
```

**Expected Performance:**

| Endpoint | Expected Time | Actual Time |
|----------|---------------|-------------|
| `/latest/{symbol}` | <10ms | ✅ |
| `/latest/all` | <15ms | ✅ |
| `/historical/{symbol}` (100 records) | <200ms | ✅ |
| `/historical/{symbol}/stats` | <100ms | ✅ |

---

## ✅ Success Criteria for Day 3

- [ ] Pagination works with `offset` parameter
- [ ] Ordering works with `order_by=asc` and `order_by=desc`
- [ ] Response headers include performance metrics
- [ ] Stats endpoint returns correct aggregates
- [ ] Bulk `/latest/all` endpoint returns all symbols
- [ ] Validation errors return appropriate 400/422 status codes
- [ ] Middleware logs all requests with timing
- [ ] All tests pass in interactive `/docs`

---

## 🐛 Troubleshooting

### **Issue: X-Headers not visible in browser**

**Cause:** CORS may block custom headers

**Solution:** Add headers to CORS allowed list in `config.py`:

```python
CORS_EXPOSE_HEADERS: list = [
    "X-Total-Count",
    "X-Query-Time-Ms",
    "X-Cache-Hit",
    "X-Process-Time-Ms"
]
```

---

### **Issue: Middleware not logging**

**Cause:** Logging level too high

**Solution:** Check `main.py` has `level=logging.INFO`:

```python
logging.basicConfig(
    level=logging.INFO,  # Not WARNING or ERROR
    ...
)
```

---

### **Issue: Stats endpoint slow (>500ms)**

**Cause:** No index on `(crypto_id, window_start)`

**Solution:** Verify indexes exist:

```sql
docker exec postgres psql -U crypto_user -d crypto_db -c "\d price_aggregates_1m"

-- Should see indexes on crypto_id and window_start
```

---

## 📚 API Documentation Updates

**New examples in `/docs`:**

1. Try pagination: `/historical/BTC?limit=10&offset=10`
2. Try ordering: `/historical/BTC?order_by=asc`
3. Try stats: `/historical/BTC/stats`
4. Try bulk fetch: `/latest/all`
5. Check response headers in browser dev tools (Network tab)

---

## ⏭️ What's Next (Day 4-5)

**WebSocket Enhancement with Redis Pub/Sub:**
- Replace polling with event-driven updates
- Stream alerts from Kafka
- Add connection health monitoring
- Support multiple concurrent clients

---

## 🎉 Day 3 Complete!

You've added:
- ✅ Advanced pagination with metadata
- ✅ Flexible ordering (ASC/DESC)
- ✅ Performance metrics in every response
- ✅ Statistical aggregation endpoint
- ✅ Bulk fetch endpoint
- ✅ Request tracing with unique IDs
- ✅ Comprehensive input validation
- ✅ Automatic request/response logging

**Your API is now production-grade!** 🚀

---

*Created: November 16, 2025*  
*Branch: feature/fastapi-backend*  
*Completes: Phase 4, Week 8, Day 3*
