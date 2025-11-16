# Redis Sink - Quick Testing Guide

Complete verification for Redis caching layer.

---

## 🚀 Quick Deploy & Test

### **Step 1: Deploy**
```bash
cd C:\Real-Time-Cryptocurrency-Market-Analyzer
WEEK7_REDIS_DEPLOY.bat
```

### **Step 2: Start Producer**
```bash
START_PRODUCER.bat
```

### **Step 3: Wait 2 minutes**

---

## ✅ Verification Commands

### **1. Check Redis Keys:**
```bash
docker exec redis redis-cli KEYS "crypto:*"
```
**Expected:** crypto:BTC:latest, crypto:ETH:latest

### **2. Get BTC Latest:**
```bash
docker exec redis redis-cli GET crypto:BTC:latest
```
**Expected:** JSON string

### **3. Get ETH Latest:**
```bash
docker exec redis redis-cli GET crypto:ETH:latest
```

### **4. Check TTL:**
```bash
docker exec redis redis-cli TTL crypto:BTC:latest
```
**Expected:** 1-300 seconds

### **5. Pretty JSON:**
```bash
docker exec redis redis-cli GET crypto:BTC:latest | python -m json.tool
```

### **6. Verify PostgreSQL:**
```bash
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT COUNT(*) FROM price_aggregates_1m;"
```
**Expected:** Still increasing (dual-sink working!)

---

## ✅ Success Criteria

- [ ] Redis keys exist
- [ ] Keys contain valid JSON
- [ ] TTL set to ~300 seconds
- [ ] PostgreSQL still working
- [ ] Job RUNNING
- [ ] No Redis errors in logs

---

**Run these commands and share results, bhau!** 🚀
