# Phase 4 - Week 8 - Day 1-2: FastAPI Backend 🚀

## 🎯 What We Built

**Production-grade REST API** with FastAPI for cryptocurrency market data access.

---

## 📦 Files Created

### **API Structure:**

```
src/api/
├── __init__.py               # Package initialization
├── main.py                   # FastAPI application
├── config.py                 # Settings management
├── database.py               # Connection pooling (Redis + PostgreSQL)
├── models.py                 # Pydantic models for validation
└── endpoints/
    ├── __init__.py
    ├── latest.py             # GET /latest/{symbol} - Redis cache
    ├── historical.py         # GET /historical/{symbol} - PostgreSQL
    └── websocket.py          # WebSocket /ws/prices/{symbol}
```

### **Configuration Files:**
- `requirements-api.txt` - FastAPI dependencies
- `START_API.bat` - Launcher script

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────┐
│           FastAPI Application                   │
│  (Auto-generated docs at /docs)                 │
└───────────┬─────────────────────┬───────────────┘
            │                     │
            ▼                     ▼
    ┌─────────────┐      ┌──────────────┐
    │    Redis    │      │  PostgreSQL  │
    │   (Latest)  │      │ (Historical) │
    └─────────────┘      └──────────────┘
```

---

## 🚀 Installation & Setup

### **Step 1: Install Dependencies**

```powershell
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Activate virtual environment
venv\Scripts\activate

# Install FastAPI dependencies
pip install -r requirements-api.txt
```

**Expected packages:**
- `fastapi==0.115.5`
- `uvicorn[standard]==0.32.1`
- `psycopg2-binary==2.9.10`
- `redis==5.2.1`
- `asyncpg==0.30.0`
- `pydantic==2.10.3`

---

### **Step 2: Verify Infrastructure is Running**

```powershell
# Check all Docker containers
docker-compose ps

# Should see 8 containers: kafka, zookeeper, postgres, redis, 
# flink-jobmanager, flink-taskmanager, kafka-ui, pgadmin
```

**If containers are stopped:**
```powershell
docker-compose up -d
timeout /t 30
```

---

### **Step 3: Verify Data Pipeline is Running**

```powershell
# Check Redis has cached data
docker exec redis redis-cli KEYS "crypto:*"
# Should see: crypto:BTC:latest, crypto:ETH:latest

# Check PostgreSQL has historical data
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"
# Should see: count > 0
```

**If no data:**
```powershell
# Start producer
START_PRODUCER.bat

# Wait 2-3 minutes for windows to complete
```

---

### **Step 4: Start FastAPI Server**

```powershell
# Launch API
START_API.bat
```

**Expected output:**
```
======================================
  Starting Crypto Market Analyzer API
======================================

[INFO] Activating virtual environment...
[INFO] Starting FastAPI server on http://localhost:8000
[INFO] API Documentation: http://localhost:8000/docs
[INFO] WebSocket Test: http://localhost:8000/ws/test

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
============================================================
🚀 Starting Crypto Market Analyzer API v1.0.0
============================================================
INFO:     ✅ Redis connection established
INFO:     ✅ PostgreSQL connection pool created
============================================================
✅ All services initialized successfully!
📡 API running at: http://0.0.0.0:8000
📚 API docs: http://localhost:8000/docs
🔌 WebSocket test: http://localhost:8000/ws/test
============================================================
```

---

## ✅ Testing the API

### **1. Health Check**

```powershell
curl http://localhost:8000/health
```

**Expected response:**
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

---

### **2. Root Endpoint**

```powershell
curl http://localhost:8000/
```

**Expected response:**
```json
{
  "message": "Crypto Market Analyzer API",
  "version": "1.0.0",
  "docs": "/docs",
  "redoc": "/redoc",
  "health": "/health",
  "websocket_test": "/ws/test"
}
```

---

### **3. Get Latest BTC Price (Redis)**

```powershell
curl http://localhost:8000/api/v1/latest/BTC
```

**Expected response:**
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

---

### **4. Get Latest ETH Price**

```powershell
curl http://localhost:8000/api/v1/latest/ETH
```

---

### **5. Get Historical Data (Last 24 Hours)**

```powershell
curl "http://localhost:8000/api/v1/historical/BTC?limit=10"
```

**Expected response:**
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
  },
  ...
]
```

---

### **6. Get Historical Data with Date Range**

```powershell
curl "http://localhost:8000/api/v1/historical/BTC?start_time=2025-11-16T00:00:00&end_time=2025-11-16T12:00:00&limit=50"
```

---

### **7. Interactive API Documentation**

Open browser to: **http://localhost:8000/docs**

**Features:**
- ✅ Auto-generated from code
- ✅ Interactive "Try it out" buttons
- ✅ Request/response examples
- ✅ Schema definitions
- ✅ Authentication support (future)

**Try this:**
1. Click on `GET /api/v1/latest/{symbol}`
2. Click "Try it out"
3. Enter `BTC` in symbol field
4. Click "Execute"
5. See live response!

---

### **8. Alternative Documentation (ReDoc)**

Open browser to: **http://localhost:8000/redoc**

More polished, better for reading documentation.

---

## 🔌 WebSocket Testing

### **Option 1: Browser Test Page**

1. Open: **http://localhost:8000/ws/test**
2. Click "Connect BTC" or "Connect ETH"
3. Watch live price updates every 2 seconds!

---

### **Option 2: JavaScript Console**

```javascript
// Open browser console (F12), paste this:

const ws = new WebSocket('ws://localhost:8000/ws/prices/BTC');

ws.onopen = () => {
    console.log('✅ Connected to BTC price stream');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('📊 Price update:', data);
};

ws.onerror = (error) => {
    console.error('❌ WebSocket error:', error);
};

ws.onclose = () => {
    console.log('❌ Disconnected');
};

// To disconnect: ws.close();
```

---

### **Option 3: Python Test Script**

Create `test_websocket.py`:

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/prices/BTC"
    
    async with websockets.connect(uri) as websocket:
        print("✅ Connected to BTC price stream")
        
        # Receive 10 messages
        for i in range(10):
            message = await websocket.recv()
            data = json.loads(message)
            print(f"📊 Message {i+1}: {data}")

asyncio.run(test_websocket())
```

Run: `python test_websocket.py`

---

## 🎓 Interview Talking Points

### **1. FastAPI Choice**

> "I chose FastAPI for its automatic API documentation, async support, and Pydantic data validation. The auto-generated /docs endpoint provides interactive API exploration for stakeholders without writing any documentation code. FastAPI's dependency injection pattern allowed me to implement connection pooling cleanly with `Depends()`."

### **2. Connection Pooling**

> "I implemented connection pooling for both Redis and PostgreSQL using a singleton DatabaseManager class. The PostgreSQL pool maintains 1-10 connections, preventing connection exhaustion under load. Redis uses built-in connection pooling with health checks every 30 seconds. This design pattern ensures resources are reused efficiently."

### **3. Error Handling & Validation**

> "I used Pydantic models for request/response validation, which provides automatic type checking and serialization. Each endpoint has explicit error responses (404, 500) with detailed error messages. The global exception handler catches unhandled errors and logs them for debugging while returning sanitized responses to clients."

### **4. REST vs WebSocket**

> "I implemented both REST endpoints for point-in-time queries and WebSocket for real-time streaming. REST is ideal for historical analysis with pagination, while WebSocket efficiently pushes updates without polling overhead. The WebSocket implementation uses a ConnectionManager to broadcast updates to multiple clients simultaneously."

---

## 🐛 Troubleshooting

### **Issue: ModuleNotFoundError: No module named 'fastapi'**

```powershell
# Solution: Install dependencies
pip install -r requirements-api.txt
```

---

### **Issue: Port 8000 already in use**

```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or change port in config.py:
# API_PORT: int = 8001
```

---

### **Issue: API returns 404 for /latest/BTC**

**Cause:** No data in Redis cache

**Solution:**
```powershell
# 1. Check Redis
docker exec redis redis-cli GET crypto:BTC:latest

# 2. If null, start producer
START_PRODUCER.bat

# 3. Wait 2 minutes for windows to complete

# 4. Verify Redis again
docker exec redis redis-cli GET crypto:BTC:latest
```

---

### **Issue: Database connection failed**

**Cause:** PostgreSQL container not running or wrong port

**Solution:**
```powershell
# 1. Check container
docker-compose ps

# 2. If stopped, start it
docker-compose up -d postgres

# 3. Verify connection
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT 1;"

# 4. Check config.py has correct port (5433, not 5432)
```

---

### **Issue: CORS errors in browser**

**Cause:** Frontend origin not in CORS_ORIGINS

**Solution:** Add origin in `config.py`:

```python
CORS_ORIGINS: list = [
    "http://localhost:8501",  # Streamlit
    "http://localhost:3000",  # React
    "http://localhost:5173"   # Vite
]
```

---

## 📊 API Performance

**Expected Performance:**
- **Latest endpoint:** <10ms (Redis cache lookup)
- **Historical endpoint:** 50-200ms (PostgreSQL query with 100 records)
- **WebSocket latency:** <50ms (polling every 2 seconds)

**Optimization Tips:**
- Redis cache hit ratio should be >99%
- PostgreSQL queries use indexes on `(crypto_id, window_start)`
- Connection pooling prevents connection overhead

---

## ✅ Success Criteria for Day 1-2

- [ ] FastAPI server starts without errors
- [ ] Health check returns "healthy" status
- [ ] `/latest/BTC` returns current price from Redis
- [ ] `/latest/ETH` returns current price from Redis
- [ ] `/historical/BTC` returns array of OHLC records
- [ ] `/docs` shows interactive API documentation
- [ ] WebSocket test page connects successfully
- [ ] Console logs show price updates every 2 seconds

---

## ⏭️ What's Next

**Day 3 (Week 8):**
- Test all endpoints with curl/Postman
- Add query parameter validation
- Error handling improvements

**Day 4-5 (Week 8):**
- Enhance WebSocket with Redis Pub/Sub
- Add real-time alerts streaming
- Performance testing

---

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Models](https://docs.pydantic.dev/)
- [Uvicorn Server](https://www.uvicorn.org/)
- [WebSocket Guide](https://fastapi.tiangolo.com/advanced/websockets/)

---

**Status: ✅ Ready to test!**

*Created: November 16, 2025*  
*Branch: feature/fastapi-backend*  
*Completes: Phase 4, Week 8, Day 1-2*
