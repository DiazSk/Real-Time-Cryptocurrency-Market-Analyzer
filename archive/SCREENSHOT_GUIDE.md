# Screenshot Organization Guide - Phase 5

## 📸 Required Screenshots for Portfolio

### Screenshot Checklist

Create a `docs/screenshots/` directory and capture these images:

---

## 1. Dashboard Screenshots

### **dashboard-overview.png** ⭐ PRIORITY
**What to capture:**
- Full dashboard view showing all sections
- Price cards at top
- Quick stats bar
- One chart visible (candlestick recommended)
- Footer with data flow

**Settings:**
- Timeframe: 1 Hour
- Chart Style: Candlestick
- View: Both (Side by Side)

**Use for:**
- README hero image
- LinkedIn posts
- Resume project section

---

### **dashboard-candlestick-dual.png** ⭐ PRIORITY
**What to capture:**
- BTC and ETH candlestick charts side by side
- Volume bars visible below both
- Mix of green/red candles

**Settings:**
- Timeframe: 1 Hour
- Chart Style: Candlestick  
- View: Both (Side by Side)

**Use for:**
- README features section
- Portfolio website
- GitHub social preview

---

### **dashboard-candlestick-btc.png**
**What to capture:**
- Full-width BTC candlestick chart
- Volume bars clearly visible
- Good mix of colors

**Settings:**
- Timeframe: 1 Hour
- Chart Style: Candlestick
- View: BTC

**Use for:**
- Detailed feature showcase
- Blog posts about project

---

### **dashboard-candlestick-ma.png** ⭐ PRIORITY
**What to capture:**
- Candlesticks with blue/orange MA lines
- Legend showing "BTC" and "20-Period MA"
- Volume bars below

**Settings:**
- Timeframe: 1 Hour (need 50+ candles for 50-MA)
- Chart Style: Candlestick with MA
- View: BTC

**Use for:**
- Technical analysis showcase
- "Advanced features" section
- Most impressive screenshot

---

### **dashboard-line-chart-comparison.png**
**What to capture:**
- BTC (blue) and ETH (orange) on dual y-axis
- Both lines visible and correlated
- Shows price movement clearly

**Settings:**
- Chart Style: Line Chart
- View: Both (Side by Side)

**Use for:**
- Alternative visualization demo
- Comparison analysis showcase

---

### **dashboard-alerts-panel.png**
**What to capture:**
- Alert panel showing 1-2 alerts
- Icons (🚀 or 📉) visible
- Price change percentages
- Timestamps

**Setup:**
- Trigger: `python test_spike.py`
- Wait: 2 minutes
- Refresh dashboard

**Use for:**
- Anomaly detection feature
- Real-time capabilities

---

### **dashboard-sidebar-alerts.png**
**What to capture:**
- Left sidebar showing:
  - About section (can be collapsed)
  - Recent alerts list
  - System status (green checkmarks)

**Use for:**
- UI/UX showcase
- Navigation demonstration

---

### **dashboard-enhanced-stats.png**
**What to capture:**
- 24-hour performance summary section
- All 8 metrics visible (Low, High, Avg, Change, Volume, Range, Data Points, Volatility)
- BTC and ETH side by side

**Use for:**
- Statistics feature showcase
- Data analysis capabilities

---

### **dashboard-export-buttons.png**
**What to capture:**
- Export data section with 3 download buttons
- "Download BTC", "Download ETH", "Download Both"

**Use for:**
- Export functionality demo
- Complete feature list

---

## 2. API Screenshots

### **api-interactive-docs.png**
**What to capture:**
- FastAPI auto-generated docs at http://localhost:8000/docs
- Expand one endpoint (e.g., /latest/BTC)
- Show "Try it out" button

**Use for:**
- API documentation showcase
- Backend capabilities

---

### **api-websocket-test.png**
**What to capture:**
- WebSocket test page at http://localhost:8000/ws/test
- Connected state with messages flowing
- Show Pub/Sub mode indicator

**Use for:**
- Real-time capabilities
- WebSocket implementation

---

## 3. Infrastructure Screenshots

### **flink-web-ui.png**
**What to capture:**
- Flink Web UI at http://localhost:8082
- Running job visible
- Task metrics (records in/out)

**Use for:**
- Stream processing showcase
- Infrastructure overview

---

### **kafka-ui.png**
**What to capture:**
- Kafka UI at http://localhost:8081
- crypto-prices topic visible
- Messages flowing

**Use for:**
- Message queue demonstration
- Infrastructure completeness

---

## 4. Code Screenshots (Optional)

### **code-flink-aggregator.png**
**What to capture:**
- `CryptoPriceAggregator.java` showing window logic
- Clean, readable code
- Syntax highlighting

**Use for:**
- Code quality showcase
- Technical depth demonstration

---

### **code-api-endpoint.png**
**What to capture:**
- One FastAPI endpoint implementation
- Shows Pydantic models, error handling

**Use for:**
- Backend code quality
- API design patterns

---

## 📁 File Organization

```
docs/screenshots/
├── dashboard-overview.png              ⭐ Hero image
├── dashboard-candlestick-dual.png      ⭐ Primary feature
├── dashboard-candlestick-ma.png        ⭐ Technical analysis
├── dashboard-candlestick-btc.png
├── dashboard-candlestick-eth.png
├── dashboard-line-chart-comparison.png
├── dashboard-alerts-panel.png
├── dashboard-sidebar-alerts.png
├── dashboard-enhanced-stats.png
├── dashboard-export-buttons.png
├── api-interactive-docs.png
├── api-websocket-test.png
├── flink-web-ui.png
├── kafka-ui.png
└── architecture-diagram.png            ⭐ System overview
```

---

## 🎨 Screenshot Best Practices

### Technical Quality
- **Resolution**: 1920x1080 or higher
- **Format**: PNG (lossless)
- **File Size**: <2MB per image (compress if needed)
- **Aspect Ratio**: 16:9 for presentations

### Composition
- **Full Window**: Capture entire browser window
- **Clean**: Close unnecessary tabs/windows
- **Readable**: Ensure text is legible at thumbnail size
- **Highlight**: Use arrows/boxes to highlight key features (optional)

### Timing
- **Wait for Data**: Ensure charts have loaded completely
- **Good Examples**: Mix of green/red candles is visually interesting
- **Avoid Empty States**: No "Loading..." or "No data" messages

### Tools
- **Windows**: Snipping Tool, Snip & Sketch, or Win+Shift+S
- **Screenshot**: Clear browser clutter first
- **Naming**: Use descriptive names matching checklist above

---

## 📝 Adding Screenshots to README

### In README.md, add image references:

```markdown
## Dashboard Preview

### Live Price Monitoring
![Dashboard Overview](docs/screenshots/dashboard-overview.png)

### Professional Candlestick Charts
![Candlestick Charts](docs/screenshots/dashboard-candlestick-dual.png)

### Technical Analysis
![Moving Averages](docs/screenshots/dashboard-candlestick-ma.png)
```

### For GitHub Social Preview

1. Go to repository settings
2. Scroll to "Social preview"
3. Upload: `dashboard-candlestick-ma.png`
4. This appears when sharing on social media

---

## ✅ Screenshot Capture Workflow

```
1. Ensure all services running (docker-compose ps)
2. Start producer (START_PRODUCER.bat)
3. Wait 15-20 minutes for good data variety
4. Start API (START_API.bat)
5. Start dashboard (START_DASHBOARD.bat)
6. Trigger spike for alerts (python test_spike.py)
7. Wait 2 minutes for alert to appear
8. Systematically capture each screenshot
9. Save to docs/screenshots/
10. Verify quality and readability
11. Add references to README
```

---

## 🎯 Priority Screenshots (Top 3)

If time limited, capture these three first:

1. **dashboard-candlestick-ma.png** - Most impressive (MA + volume)
2. **dashboard-overview.png** - Shows complete system
3. **dashboard-candlestick-dual.png** - Professional comparison

These three tell 80% of your project story visually.

---

**Status:** Ready to capture screenshots  
**Next:** Take screenshots, add to README, commit
