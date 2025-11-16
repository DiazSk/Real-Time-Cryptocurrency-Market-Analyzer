# API Testing Guide - Quick Reference

## 🚀 Quick Start

```powershell
# 1. Start infrastructure
docker-compose up -d

# 2. Start data pipeline
START_PRODUCER.bat

# 3. Wait 2 minutes for data

# 4. Start API
START_API.bat

# 5. Test API
curl http://localhost:8000/health
```

---

## 📋 Endpoint Quick Reference

### **Base URL:** `http://localhost:8000`

| Method | Endpoint | Description | Response Time |
|--------|----------|-------------|---------------|
| GET | `/` | API info | <5ms |
| GET | `/health` | Health check | <50ms |
| GET | `/docs` | Interactive docs | Browser |
| GET | `/api/v1/latest/{symbol}` | Latest price (Redis) | <10ms |
| GET | `/api/v1/historical/{symbol}` | Historical data (PostgreSQL) | 50-200ms |
| GET | `/api/v1/historical/{symbol}/latest` | Latest from DB | <50ms |
| WS | `/ws/prices/{symbol}` | WebSocket stream | Real-time |
| GET | `/ws/test` | WebSocket test page | Browser |

---

## 🧪 Test Commands

### **1. Health Check**
```bash
curl http://localhost:8000/health | python -m json.tool
```

### **2. Latest BTC Price**
```bash
curl http://localhost:8000/api/v1/latest/BTC | python -m json.tool
```

### **3. Latest ETH Price**
```bash
curl http://localhost:8000/api/v1/latest/ETH | python -m json.tool
```

### **4. Last 10 BTC Candles**
```bash
curl "http://localhost:8000/api/v1/historical/BTC?limit=10" | python -m json.tool
```

### **5. BTC Data for Specific Time Range**
```bash
curl "http://localhost:8000/api/v1/historical/BTC?start_time=2025-11-16T00:00:00&end_time=2025-11-16T23:59:59&limit=100" | python -m json.tool
```

### **6. Latest from Database**
```bash
curl "http://localhost:8000/api/v1/historical/BTC/latest" | python -m json.tool
```

---

## 🔌 WebSocket Testing

### **Browser Console Test**

```javascript
// Open http://localhost:8000/ws/test
// OR open browser console (F12) and paste:

const ws = new WebSocket('ws://localhost:8000/ws/prices/BTC');

ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    console.log(data);
};

// Watch for price updates!
// To disconnect: ws.close();
```

---

## 🎯 Expected Responses

### **Health Check (Healthy)**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-16T12:00:00.123456",
  "services": {
    "redis": "healthy",
    "postgresql": "healthy"
  }
}
```

### **Latest Price Response**
```json
{
  "symbol": "BTC",
  "window_start": "2025-11-16T12:30:00+00:00",
  "window_end": "2025-11-16T12:31:00+00:00",
  "open": 95750.00,
  "high": 95800.00,
  "low": 95700.00,
  "close": 95780.00,
  "volume_sum": 78701577213.28,
  "event_count": 12
}
```

### **Historical Data Response**
```json
[
  {
    "symbol": "BTC",
    "window_start": "2025-11-16T12:30:00",
    "window_end": "2025-11-16T12:31:00",
    "open_price": 95750.00,
    "high_price": 95800.00,
    "low_price": 95700.00,
    "close_price": 95780.00,
    "avg_price": 95757.50,
    "volume_sum": 78701577213.28,
    "trade_count": 12
  }
]
```

### **WebSocket Message**
```json
{
  "type": "price_update",
  "symbol": "BTC",
  "data": {
    "symbol": "BTC",
    "windowStart": "2025-11-16T12:30:00Z",
    "windowEnd": "2025-11-16T12:31:00Z",
    "open": 95750.00,
    "high": 95800.00,
    "low": 95700.00,
    "close": 95780.00,
    "volumeSum": 78701577213.28,
    "eventCount": 12
  },
  "timestamp": "2025-11-16T12:30:15.123456"
}
```

---

## ⚠️ Common Issues

### **1. 404 Not Found for /latest/BTC**
```bash
# Check Redis has data
docker exec redis redis-cli GET crypto:BTC:latest

# If null, start producer and wait 2 minutes
START_PRODUCER.bat
```

### **2. 500 Internal Server Error**
```bash
# Check API logs
# Look for connection errors

# Verify services are running
docker-compose ps

# Check health endpoint
curl http://localhost:8000/health
```

### **3. Empty Historical Data**
```bash
# Check PostgreSQL has data
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"

# Should be > 0
```

### **4. WebSocket Connection Refused**
- Ensure API is running
- Check browser console for CORS errors
- Verify URL: `ws://localhost:8000/ws/prices/BTC`

---

## 📊 Performance Benchmarks

```bash
# Benchmark latest endpoint (10 requests)
for i in {1..10}; do
    time curl -s http://localhost:8000/api/v1/latest/BTC > /dev/null
done

# Expected: <10ms per request
```

---

## 🎓 Interactive Testing

**Use FastAPI's Built-in Docs:**

1. Open: http://localhost:8000/docs
2. Expand any endpoint
3. Click "Try it out"
4. Fill parameters
5. Click "Execute"
6. See response in real-time!

**Features:**
- ✅ No curl needed
- ✅ Auto-validation
- ✅ Response codes
- ✅ Schema inspection

---

## 🔄 Testing Workflow

```
1. Verify infrastructure (docker-compose ps)
   ↓
2. Check data exists (Redis + PostgreSQL)
   ↓
3. Start API (START_API.bat)
   ↓
4. Health check (curl /health)
   ↓
5. Test endpoints (curl or /docs)
   ↓
6. WebSocket test (/ws/test)
```

---

**Happy Testing! 🚀**
