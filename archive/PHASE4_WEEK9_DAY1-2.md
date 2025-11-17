# Phase 4 - Week 9 - Day 1-2: Basic Streamlit Dashboard 📊

## 🎯 What We Built

**Professional real-time dashboard** using Streamlit to visualize cryptocurrency market data from your FastAPI backend.

---

## 📦 Files Created

### **Dashboard Structure:**

```
src/dashboard/
├── app.py                           # Main Streamlit application
├── config.py                        # Dashboard configuration
├── components/
│   ├── __init__.py
│   ├── price_cards.py              # Current price display
│   ├── line_chart.py               # Price trend charts
│   └── stats.py                    # Statistics display
└── utils/
    ├── __init__.py
    ├── api_client.py               # FastAPI connection
    └── data_processor.py           # Data formatting

requirements-dashboard.txt           # Streamlit dependencies
START_DASHBOARD.bat                  # Dashboard launcher
```

---

## 🚀 Setup & Installation

### **Step 1: Install Dependencies**

```powershell
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Activate virtual environment
venv\Scripts\activate

# Install dashboard dependencies
pip install -r requirements-dashboard.txt
```

**Dependencies installed:**
- `streamlit` - Dashboard framework
- `streamlit-autorefresh` - Auto-refresh functionality
- `plotly` - Interactive charts
- `pandas` - Data manipulation
- `requests` - API calls

---

### **Step 2: Ensure Backend is Running**

The dashboard needs your FastAPI backend to be running:

```powershell
# In separate terminal
START_API.bat

# Verify API is healthy
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "services": {
    "redis": "healthy",
    "postgresql": "healthy"
  }
}
```

---

### **Step 3: Start Dashboard**

```powershell
# Launch dashboard
START_DASHBOARD.bat
```

**Expected output:**
```
======================================
  Starting Crypto Market Dashboard
======================================

[INFO] Activating virtual environment...
[INFO] Checking if API is running...
[INFO] Starting Streamlit dashboard...
[INFO] Dashboard URL: http://localhost:8501

You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

**Dashboard opens automatically in your browser!**

---

## 🎨 Dashboard Features (Day 1-2)

### **1. Live Price Cards**

```
┌─────────────────┐  ┌─────────────────┐
│  🚀 BTC          │  │  📈 ETH          │
│  $95,780        │  │  $3,154         │
│  +2.3%          │  │  +1.8%          │
│  Volume: $78.7B │  │  Volume: $35.9M │
└─────────────────┘  └─────────────────┘
```

**Features:**
- Current price from Redis cache
- Price change percentage (since window open)
- Trend emoji (🚀, 📈, ➡️, ↘️, 📉)
- Volume with abbreviations (B/M/K)
- Auto-refresh every 2 seconds

---

### **2. Quick Stats Bar**

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ BTC High    │ BTC Low     │ ETH High    │ ETH Low     │
│ $95,800     │ $95,700     │ $3,155      │ $3,152      │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

**Shows:**
- Current window high/low for BTC
- Current window high/low for ETH

---

### **3. 24-Hour Price Trend Chart**

Interactive Plotly chart with:
- Line chart showing last 24 hours
- Hover tooltips with exact price and time
- Zoom, pan, and export controls
- Dark theme matching your backend

**Three view modes:**
1. **Combined View** - BTC and ETH on same chart (dual y-axis)
2. **BTC Only** - Full-width BTC chart
3. **ETH Only** - Full-width ETH chart

---

### **4. Auto-Refresh**

Dashboard automatically refreshes every **2 seconds**:
- Fetches latest prices from `/latest/all` endpoint
- Updates all metrics and charts
- Shows last update timestamp

**You can watch prices update in real-time!**

---

## 🧪 Testing the Dashboard

### **Test 1: Verify Connection**

1. Open: http://localhost:8501
2. Dashboard should load within 5 seconds
3. Check for green "✓ API is healthy" indicator
4. See BTC and ETH price cards

**If you see errors:**
- Check API is running: `curl http://localhost:8000/health`
- Check producer is running: `START_PRODUCER.bat`
- Wait 2 minutes for data pipeline

---

### **Test 2: Verify Real-Time Updates**

1. Watch the "Last updated" timestamp in footer
2. Should refresh every 2 seconds
3. Watch price cards for changes (every 1 minute when windows complete)

**To force a change:**
```powershell
# Trigger a synthetic spike (if you have the test script)
python test_spike.py
```

---

### **Test 3: Chart Interactions**

1. Hover over chart line → See price tooltip
2. Click legend to hide/show series
3. Use zoom controls (magnifying glass icons)
4. Double-click to reset zoom
5. Export chart (camera icon)

---

### **Test 4: Multi-Tab Test**

1. Open dashboard in 2-3 browser tabs
2. All tabs auto-refresh independently
3. All show same data (same API backend)

---

## 📊 Architecture Flow

```
CoinGecko API
    ↓
Kafka (crypto-prices topic)
    ↓
Flink (OHLC aggregation)
    ↓
├─→ Redis (latest cache)
└─→ PostgreSQL (historical)
    ↓
FastAPI Backend
    ↓
Streamlit Dashboard ← YOU ARE HERE
    ↓
Your Browser
```

**Complete end-to-end pipeline!**

---

## 🎓 Interview Talking Points

### **1. Full-Stack Integration**

> "I built a complete data pipeline from API ingestion to visualization. The dashboard connects to my FastAPI backend via a custom API client class with retry logic and exponential backoff. It fetches latest prices from Redis for sub-second updates and historical data from PostgreSQL for trend analysis."

---

### **2. Real-Time Auto-Refresh**

> "The dashboard uses Streamlit's auto-refresh to poll the API every 2 seconds. This provides near real-time updates without WebSocket complexity in the UI layer. The backend pushes data via Redis Pub/Sub, and the dashboard pulls via HTTP polling—a hybrid approach that's simpler for dashboards."

---

### **3. Component Architecture**

> "I structured the dashboard using a component-based architecture with separation of concerns: API client handles all HTTP communication, data processors transform raw API responses for display, and UI components are pure rendering functions. This makes the code testable and maintainable."

---

### **4. User Experience**

> "I prioritized UX with features like automatic error handling (shows helpful messages if API is down), loading spinners during data fetch, and interactive Plotly charts that let users zoom and explore. The dashboard also gracefully degrades—if historical data is missing, only that section shows an error while latest prices still work."

---

## 🎨 Customization Options

### **Change Refresh Interval**

Edit `config.py`:
```python
REFRESH_INTERVAL = 5  # Refresh every 5 seconds instead of 2
```

---

### **Change Color Theme**

Edit `config.py`:
```python
COLORS = {
    "positive": "#00ff00",  # Bright green
    "negative": "#ff0000",  # Bright red
    ...
}
```

---

### **Add More Cryptocurrencies**

Edit `config.py`:
```python
SYMBOLS = ["BTC", "ETH", "SOL", "ADA"]  # Add more symbols

# Then update API client to support them
```

---

## 🐛 Troubleshooting

### **Issue: Dashboard shows "API is not responding"**

**Solution:**
```powershell
# Check API status
curl http://localhost:8000/health

# If not running, start it
START_API.bat
```

---

### **Issue: "No price data available"**

**Cause:** Data pipeline not running or no data in cache yet

**Solution:**
```powershell
# 1. Check Redis has data
docker exec redis redis-cli KEYS "crypto:*"
# Should see: crypto:BTC:latest, crypto:ETH:latest

# 2. If empty, start producer
START_PRODUCER.bat

# 3. Wait 2 minutes for first window to complete

# 4. Refresh dashboard (Ctrl+R in browser)
```

---

### **Issue: Charts not showing**

**Cause:** No historical data in PostgreSQL

**Solution:**
```powershell
# Check PostgreSQL has data
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"
# Should be > 0

# If empty, wait longer (need at least 2-3 minutes of data)
```

---

### **Issue: Dashboard very slow**

**Solutions:**
1. Reduce `REFRESH_INTERVAL` in `config.py` (5 seconds instead of 2)
2. Reduce historical data `limit` in API calls
3. Close other browser tabs

---

## ✅ Success Criteria for Day 1-2

- [ ] Dashboard starts without errors
- [ ] API health check passes
- [ ] BTC and ETH price cards display correctly
- [ ] Quick stats bar shows high/low prices
- [ ] 24-hour chart renders with data
- [ ] Auto-refresh works (timestamp updates every 2s)
- [ ] Chart interactions work (hover, zoom, pan)
- [ ] No console errors in browser DevTools

---

## 📸 Screenshots to Capture

For your portfolio, take screenshots of:

1. **Full dashboard view** - Showing all components
2. **Price cards close-up** - With positive/negative changes
3. **Chart with hover tooltip** - Showing interactivity
4. **Combined BTC/ETH chart** - Dual y-axis view
5. **Real-time update** - Before and after showing price change

---

## 🎉 What You Accomplished

You now have:
- ✅ **Complete web dashboard** connecting to your API
- ✅ **Real-time price updates** auto-refreshing every 2 seconds
- ✅ **Interactive visualizations** with Plotly
- ✅ **Professional UI** with Streamlit's built-in styling
- ✅ **Error handling** with helpful user messages
- ✅ **Component architecture** for maintainability

**This completes the visual layer of your project!** 🎊

---

## ⏭️ What's Next (Day 3-4)

**Candlestick Charts & Volume Bars:**
- Add professional OHLC candlestick charts
- Volume bars below price chart
- Multi-timeframe selector (1m, 5m, 15m)
- Enhanced chart interactions

**Time estimate:** 2-3 hours

---

## 📝 Git Commit

```bash
git add .
git commit -m "feat(dashboard): implement basic Streamlit dashboard with real-time updates

Week 9 Day 1-2 Complete:

Dashboard Structure:
- Created Streamlit app with component architecture
- API client with retry logic and error handling
- Data processors for formatting and transformation

Features Implemented:
- Live price cards with trend indicators
- Quick stats bar (high/low for 24h)
- 24-hour price trend charts (Plotly)
- Auto-refresh every 2 seconds
- Three chart view modes (combined, BTC only, ETH only)
- Interactive chart controls (zoom, pan, export)

User Experience:
- Automatic error handling and user feedback
- Loading spinners during data fetch
- Responsive layout with columns
- Dark theme matching backend
- Last update timestamp display

Integration:
- Connects to FastAPI backend
- Fetches from /latest and /historical endpoints
- Graceful degradation if services unavailable

Phase 4 - Week 9 - Day 1-2 complete"

git push origin feature/streamlit-dashboard
```

---

**Status: ✅ Basic Dashboard Complete!**

*Created: November 16, 2025*  
*Branch: feature/streamlit-dashboard*  
*Completes: Phase 4, Week 9, Day 1-2*
