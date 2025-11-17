# Phase 4 - Week 9 - Day 3-4: Candlestick Charts & Volume Visualization 📊

## 🎯 What We Built

**Professional trader-style visualizations** with OHLC candlestick charts, volume bars, and technical indicators.

---

## 📦 What's New

### **1. Candlestick Chart Component**
**File:** `components/candlestick_chart.py`

**Features:**
- Professional OHLC candlestick charts
- Volume bars below price chart
- Moving average overlays (20-period, 50-period)
- Three rendering modes:
  - Single candlestick with volume
  - Side-by-side dual charts
  - Candlestick with moving averages

**Color Scheme:**
- Green candles: Price increased (close > open)
- Red candles: Price decreased (close < open)
- Volume bars match candle color

---

### **2. Enhanced API Client**
**File:** `utils/api_client.py`

**New Method:**
```python
get_timeframe_data(symbol, minutes)
# Fetches last N minutes of data
# Examples: 60, 240, 720, 1440 minutes
```

**Purpose:** Flexible data fetching for different chart timeframes

---

### **3. Enhanced Main App**
**File:** `app.py`

**New Features:**
- **Timeframe Selector:** 1h, 4h, 12h, 24h
- **Chart Style Selector:** Candlestick, Line, Candlestick+MA
- **View Selector:** Both (side by side), BTC only, ETH only
- **Dynamic Data Fetching:** Only fetches what user selects

---

## 🎨 Chart Types Available

### **1. Candlestick Chart**

**What it shows:**
```
Each candle represents a 1-minute window:
- Open: Price at window start
- High: Highest price in window
- Low: Lowest price in window
- Close: Price at window end

Green candle: Close > Open (price went up)
Red candle: Close < Open (price went down)
```

**Professional Features:**
- Wick (shadow) shows high/low range
- Body shows open/close range
- Hover shows all 4 values
- Zoom and pan controls

---

### **2. Volume Bars**

**What it shows:**
```
Bars below candlesticks show trading volume
- Height: Total volume in that minute
- Color: Matches candle (green up, red down)
```

**Why it matters:**
- High volume = strong price movement
- Low volume = weak price movement
- Volume confirms trend strength

---

### **3. Moving Averages**

**What it shows:**
```
20-Period MA (Blue): Short-term trend
50-Period MA (Orange): Long-term trend

When 20-MA crosses above 50-MA: Bullish signal
When 20-MA crosses below 50-MA: Bearish signal
```

**Technical Analysis 101!**

---

## 🚀 How to Use

### **Step 1: Restart Dashboard**

If dashboard is already running:
```powershell
# Stop it (Ctrl+C in terminal)
# Restart
START_DASHBOARD.bat
```

Dashboard will reload with new features automatically!

---

### **Step 2: Select Timeframe**

In the dashboard:
1. Find "Timeframe:" dropdown
2. Select: **1 Hour**, **4 Hours**, **12 Hours**, or **24 Hours**
3. Chart updates automatically

**Note:** For meaningful candlesticks, you need at least 10-20 data points.
- 1 Hour needs ~10 minutes of producer runtime
- 4 Hours needs ~20 minutes
- 24 Hours needs ~30 minutes

---

### **Step 3: Choose Chart Style**

Select from:
- **Candlestick** - Professional OHLC with volume bars
- **Line Chart** - Simple price trend (Day 1-2 style)
- **Candlestick with MA** - Candlesticks + moving averages

**Try them all to see different perspectives!**

---

### **Step 4: Choose View**

Select from:
- **Both (Side by Side)** - BTC and ETH side by side
- **BTC** - Full-width Bitcoin chart
- **ETH** - Full-width Ethereum chart

---

## 🧪 Testing Guide

### **Test 1: Candlestick Chart Renders**

1. Dashboard running
2. Select: **1 Hour** timeframe
3. Select: **Candlestick** style
4. Select: **BTC** view
5. **Expected:** Green/red candles with volume bars below

**If "No data available":**
- Wait longer (need ~10 minutes of data)
- Check PostgreSQL: `docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"`
- Should have >10 records

---

### **Test 2: Volume Bars Display**

1. Open candlestick chart
2. Look at bottom section
3. **Expected:** Colored bars matching candle colors
4. **Hover:** Shows exact volume value

---

### **Test 3: Moving Averages**

1. Select: **Candlestick with MA** style
2. Select: **BTC** view (only works in single view)
3. **Expected:** Blue and orange lines overlaying candlesticks
4. **If not visible:** Need at least 50 data points for 50-MA

---

### **Test 4: Timeframe Switching**

1. Start with **1 Hour**
2. Switch to **4 Hours**
3. **Expected:** Chart zooms out, shows more candles
4. Switch to **24 Hours**
5. **Expected:** Full day view (if data available)

---

### **Test 5: Interactive Features**

**Hover:**
- Move mouse over candle
- See popup with Open/High/Low/Close

**Zoom:**
- Click and drag on chart
- Zooms into selected region

**Pan:**
- After zooming, drag chart left/right

**Reset:**
- Double-click to reset zoom

**Export:**
- Click camera icon (top right)
- Downloads PNG image

---

## 🎓 Interview Talking Points

### **1. Candlestick Chart Choice**

> "I implemented OHLC candlestick charts because they're industry standard for financial data visualization. Each candle shows four critical data points—open, high, low, close—in a single visual element. The color coding provides instant insight: green means buyers dominated, red means sellers dominated. This information density is why every professional trading platform uses candlesticks."

---

### **2. Volume Correlation**

> "I added volume bars below the price chart to show correlation between price movement and trading activity. High volume during a price move confirms the trend's strength, while low volume suggests weak conviction. I color-coded the volume bars to match their candles—green bars for up candles, red for down—making it intuitive to spot volume-price divergences."

---

### **3. Moving Averages as Technical Indicators**

> "I implemented simple moving averages as optional technical indicators. The 20-period MA captures short-term trends, while the 50-period MA shows longer-term momentum. When the fast MA crosses above the slow MA, it's a bullish signal. This demonstrates understanding of technical analysis concepts used by quantitative traders."

---

### **4. Multi-Timeframe Analysis**

> "I added a timeframe selector because traders analyze at multiple scales. Short-term traders want 1-hour views for quick decisions, while position traders need 24-hour views for broader trends. Supporting multiple timeframes in the same interface demonstrates understanding of different trading strategies and user personas."

---

### **5. Plotly for Interactivity**

> "I chose Plotly for visualization because it provides professional-grade interactive charts with zero JavaScript. Users can zoom, pan, and export charts. The library also handles responsive design automatically, so charts look good on any screen size. This balance of power and simplicity makes it ideal for data science dashboards."

---

## 📊 Chart Anatomy

### **Candlestick Explained:**

```
       │ ← High (top of wick)
       │
    ┌──┴──┐
    │     │ ← Close (top of body for green candle)
    │     │
    └──┬──┘ ← Open (bottom of body for green candle)
       │
       │ ← Low (bottom of wick)
```

**Green Candle (Bullish):**
- Body: Open (bottom) to Close (top)
- Wick: Shows high/low extremes
- Meaning: Price increased

**Red Candle (Bearish):**
- Body: Open (top) to Close (bottom)
- Wick: Shows high/low extremes
- Meaning: Price decreased

---

## 🎨 Visual Design Principles

### **Color Psychology:**
- **Green (#26a69a):** Positive, growth, bullish
- **Red (#ef5350):** Negative, decline, bearish
- **Blue (#2196F3):** Neutral, informational (MA lines)
- **Orange (#FF9800):** Secondary indicator
- **Dark Background (#0e1117):** Reduces eye strain

### **Layout Hierarchy:**
1. **Primary:** Price cards (most important info)
2. **Secondary:** Quick stats (context)
3. **Tertiary:** Charts (detailed analysis)
4. **Footer:** Metadata (timestamps, data flow)

---

## 📸 Screenshot Checklist for Day 3-4

Capture these new screenshots:

### **1. Candlestick Chart View**
- **Timeframe:** 1 Hour
- **Style:** Candlestick
- **View:** BTC
- **Shows:** Green/red candles with volume bars
- **File:** `dashboard-candlestick-btc.png`

### **2. Dual Candlestick View**
- **View:** Both (Side by Side)
- **Shows:** BTC and ETH charts together
- **File:** `dashboard-candlestick-dual.png`

### **3. Moving Averages View**
- **Style:** Candlestick with MA
- **Shows:** Candles + blue/orange MA lines
- **File:** `dashboard-candlestick-ma.png`

### **4. Volume Correlation**
- **Zoom:** Into volume bars
- **Shows:** Volume matching candle colors
- **File:** `dashboard-volume-bars.png`

### **5. Chart Interaction**
- **Action:** Hover over candle
- **Shows:** Tooltip with OHLC values
- **File:** `dashboard-candlestick-hover.png`

---

## 🐛 Troubleshooting

### **Issue: Candlesticks look weird (all same height)**

**Cause:** Not enough data variation yet

**Solution:**
- Wait longer (20-30 minutes for more data)
- Or trigger synthetic spike:
  ```powershell
  python test_spike.py
  ```

---

### **Issue: Volume bars not showing**

**Cause:** 'volume' column missing or zero

**Check:**
```bash
curl "http://localhost:8000/api/v1/historical/BTC?limit=5"
# Verify volume_sum field exists and > 0
```

---

### **Issue: Moving averages not visible**

**Cause:** Not enough data points (need 50+ candles for 50-MA)

**Solution:**
- Use shorter MA periods (10, 20 instead of 20, 50)
- Or wait for more data accumulation
- Select "1 Hour" view (requires less data)

---

### **Issue: Chart is empty**

**Cause:** Selected timeframe has no data yet

**Solutions:**
1. Choose shorter timeframe (1 Hour instead of 24 Hours)
2. Wait for more data accumulation
3. Check API returns data:
   ```bash
   curl "http://localhost:8000/api/v1/historical/BTC?limit=10"
   ```

---

## ✅ Success Criteria for Day 3-4

- [ ] Dashboard loads with new selectors (Timeframe, Chart Style, View)
- [ ] Candlestick chart renders with green/red candles
- [ ] Volume bars appear below price chart
- [ ] Volume bar colors match candle colors
- [ ] Can switch between 1h/4h/12h/24h timeframes
- [ ] Can switch between Candlestick/Line/MA styles
- [ ] Can switch between Both/BTC/ETH views
- [ ] Hover shows OHLC tooltip
- [ ] Chart is interactive (zoom, pan work)
- [ ] Moving averages display (when enough data)

---

## 🎯 Features Comparison

| Feature | Day 1-2 (Basic) | Day 3-4 (Enhanced) |
|---------|----------------|-------------------|
| **Chart Type** | Line only | Candlestick + Line + MA |
| **Timeframes** | 24h only | 1h, 4h, 12h, 24h |
| **Views** | Combined/BTC/ETH | Both/BTC/ETH + side-by-side |
| **Volume** | Not shown | Volume bars |
| **Technical Indicators** | None | Moving averages |
| **Interactivity** | Basic | Advanced (tooltips, zoom) |
| **Professional Look** | Good | **Excellent** |

---

## 🎓 What You're Learning

### **Financial Data Visualization:**
- OHLC representation
- Candlestick patterns
- Volume-price relationships
- Technical indicators

### **Streamlit Advanced Features:**
- Multiple selector widgets
- Conditional rendering
- Subplot layouts
- Dynamic data fetching

### **Plotly Advanced:**
- Candlestick traces
- Subplot creation
- Multiple y-axes
- Custom hover templates

---

## 📊 Complete Feature Set

After Day 3-4, your dashboard has:

### **Live Data:**
- ✅ Current prices (Redis cache)
- ✅ Price change indicators
- ✅ Volume display
- ✅ High/low stats

### **Historical Visualization:**
- ✅ Line charts
- ✅ **Candlestick charts** ← NEW
- ✅ **Volume bars** ← NEW
- ✅ **Moving averages** ← NEW
- ✅ **Multi-timeframe views** ← NEW

### **Interactivity:**
- ✅ Auto-refresh (2s)
- ✅ Hover tooltips
- ✅ Zoom/pan controls
- ✅ View switching
- ✅ Chart export

### **Professional Touch:**
- ✅ Dark theme
- ✅ Color-coded metrics
- ✅ Responsive layout
- ✅ Error handling
- ✅ Loading states

---

## 🎉 What This Demonstrates

### **For Recruiters:**
> "My dashboard uses professional financial visualization techniques like candlestick charts and volume correlation. I implemented multiple timeframe analysis (1h to 24h) and technical indicators like moving averages. The interface is fully interactive with Plotly's enterprise-grade charting library."

### **For Technical Interviews:**
> "I chose candlestick charts over simple line charts because they encode four data points per timestamp—open, high, low, close—providing richer information density. The volume subplot uses the same x-axis scale for correlation analysis. I implemented this using Plotly's subplot system with shared axes and synchronized zooming."

---

## ⏭️ What's Next: Day 5-7

**Final Polish:**
- Alert notifications (show recent anomalies)
- Price statistics cards (24h high/low/average)
- Dark/light theme toggle
- Export data to CSV
- Professional screenshots and demo video

**Time:** 2-3 hours  
**Outcome:** Portfolio-ready project with all features

---

## 📝 Git Commit

```bash
git add .
git commit -m "feat(dashboard): add candlestick charts and volume visualization

Week 9 Day 3-4 Complete:

New Components:
- Professional OHLC candlestick charts
- Volume bars with color-coded correlation
- Moving average overlays (20/50 period)
- Three chart rendering modes

Enhanced Features:
- Timeframe selector (1h, 4h, 12h, 24h)
- Chart style selector (Candlestick, Line, MA)
- View selector (Both, BTC only, ETH only)
- Dynamic data fetching based on user selection

Visualization Improvements:
- Green/red color scheme for price direction
- Volume bars matching candle colors
- Interactive tooltips with OHLC values
- Synchronized zoom/pan across subplots
- Professional dark theme

API Client Enhancement:
- Added get_timeframe_data() method
- Flexible minute-based data fetching

This provides trader-style professional visualization
demonstrating financial data analysis capabilities.

Phase 4 - Week 9 - Day 3-4 complete"

git push origin feature/streamlit-dashboard
```

---

## 🎊 Congratulations!

Your dashboard now has:
- ✅ **Professional candlestick charts** (like Bloomberg Terminal)
- ✅ **Volume analysis** (like TradingView)
- ✅ **Technical indicators** (like real trading platforms)
- ✅ **Multi-timeframe views** (like professional tools)

**This is portfolio gold!** 📸

---

**Status: ✅ Day 3-4 Complete**  
**Next: Day 5-7 - Final Polish**  
**Branch: feature/streamlit-dashboard**

---

*Amazing work! Your dashboard is now professional-grade!* 🎉
