# Dashboard Quick Start - Week 9 Day 1-2

## 🚀 Launch in 3 Steps

### **1. Install Dependencies**
```powershell
pip install -r requirements-dashboard.txt
```

### **2. Start API (if not already running)**
```powershell
START_API.bat
```

### **3. Launch Dashboard**
```powershell
START_DASHBOARD.bat
```

**Opens automatically at:** http://localhost:8501

---

## ✅ Quick Health Check

Run this after dashboard opens:

- [ ] Dashboard loads in browser
- [ ] See BTC and ETH price cards
- [ ] See 24-hour chart
- [ ] "Last updated" timestamp refreshes every 2s
- [ ] No red error messages

---

## 🐛 Troubleshooting

### **"API is not responding"**
```powershell
# Check API
curl http://localhost:8000/health

# If not running
START_API.bat
```

### **"No price data available"**
```powershell
# Check Redis
docker exec redis redis-cli KEYS "crypto:*"

# If empty, start producer
START_PRODUCER.bat
# Wait 2 minutes
```

### **Charts not showing**
```powershell
# Check PostgreSQL
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"

# Need at least a few records
# Wait 3-5 minutes for data accumulation
```

---

## 📸 Screenshot Checklist

Capture these for your portfolio:

1. [ ] Full dashboard view
2. [ ] Price cards close-up
3. [ ] Chart with hover tooltip
4. [ ] Combined BTC/ETH chart
5. [ ] Before/after showing price change

---

## 🎯 Demo Readiness

Test these before showing recruiters:

- [ ] Dashboard loads in <5 seconds
- [ ] All prices visible and accurate
- [ ] Charts are interactive (hover works)
- [ ] Auto-refresh working (timestamp updates)
- [ ] Can switch between chart views
- [ ] No console errors (F12 in browser)

---

## ⏭️ Next Steps

After verifying Day 1-2 works:

1. Take screenshots
2. Commit to Git
3. Ready for Day 3-4 (Candlestick charts!)

---

**You're almost done with Week 9!** 🎉
