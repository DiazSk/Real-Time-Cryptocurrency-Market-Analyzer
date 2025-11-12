# Phase 2 - Week 3 - Day 1-2 Checklist

## 🎯 Goal: Get Kafka stack running with UI

### Pre-requisites
- [ ] Docker Desktop installed and running
- [ ] Repository cloned
- [ ] Terminal/PowerShell ready

---

## 📝 Step-by-Step Tasks

### 1. Start Infrastructure (5 mins)

```bash
# Navigate to project directory
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Start all services in detached mode
docker-compose up -d
```

**Wait 30-60 seconds for all services to start**

---

### 2. Verify Services (5 mins)

```bash
# Check all containers are running
docker-compose ps

# Should see:
# - zookeeper    Up
# - kafka        Up  
# - kafka-ui     Up
```

If any container shows "Restarting" or "Exit":
```bash
# Check logs for that service
docker-compose logs zookeeper
docker-compose logs kafka
docker-compose logs kafka-ui
```

---

### 3. Access Kafka UI (10 mins)

1. Open browser: **http://localhost:8080**
2. You should see: "Clusters: local"
3. Click on "local" cluster
4. Explore:
   - Brokers tab (should show 1 broker)
   - Topics tab (empty for now)

---

### 4. Create Test Topic (10 mins)

**In Kafka UI:**

1. Go to **Topics** → **Add a Topic**
2. Fill in:
   - **Name**: `test-topic`
   - **Number of partitions**: `3`
   - **Replication Factor**: `1`
   - **Min In Sync Replicas**: `1`
3. Click **Create Topic**

4. Click on your new topic to see:
   - Overview
   - Messages (empty)
   - Consumers (none yet)
   - Settings

---

### 5. Produce Test Message (15 mins)

**In Kafka UI → test-topic → Messages:**

1. Click **Produce Message**
2. Add test data:
   ```json
   {
     "test": "hello kafka",
     "timestamp": "2025-01-11T10:00:00Z"
   }
   ```
3. Click **Produce Message**
4. Refresh - you should see your message!

---

### 6. Understanding What You Built (15 mins)

**Zookeeper (Port 2181):**
- Manages Kafka cluster metadata
- Tracks which brokers are alive
- Stores topic configurations

**Kafka (Port 9092):**
- Message broker
- Stores messages in topics
- Handles producer/consumer connections

**Kafka UI (Port 8080):**
- Visual interface for Kafka
- Makes debugging easier
- Shows messages, topics, consumers in real-time

---

## ✅ Success Criteria

- [ ] All 3 containers running (`docker-compose ps`)
- [ ] Kafka UI accessible at http://localhost:8080
- [ ] Created `test-topic` with 3 partitions
- [ ] Produced at least 1 test message
- [ ] Can view message in Kafka UI

---

## 🐛 Troubleshooting Guide

### Problem: Port 9092 already in use

**Check what's using it:**
```bash
# PowerShell
netstat -ano | findstr :9092
```

**Solution:**
```bash
# Stop the process
taskkill /PID <process_id> /F

# Or change port in docker-compose.yml
# Edit kafka service ports to "9093:9092"
```

---

### Problem: Kafka container keeps restarting

**Check logs:**
```bash
docker-compose logs kafka
```

**Common causes:**
- Zookeeper not ready yet (wait 30s)
- Ports already in use
- Docker resources low (increase in Docker Desktop)

**Solution:**
```bash
# Restart with fresh state
docker-compose down
docker-compose up -d
```

---

### Problem: Can't access Kafka UI

**Solutions:**
1. Clear browser cache
2. Try `http://127.0.0.1:8080` instead
3. Restart UI:
   ```bash
   docker-compose restart kafka-ui
   ```

---

### Problem: "Connection refused" errors

**Check Docker Desktop:**
- Is Docker Desktop running?
- Are containers showing in Docker Desktop UI?
- Try restarting Docker Desktop

---

## 📸 Take Screenshots For Portfolio

Capture these for your project documentation:
1. `docker-compose ps` output showing all services up
2. Kafka UI main dashboard
3. Test topic overview
4. A message you produced

---

## 🎓 Interview Questions to Prepare

After completing this:

**Q: Why Zookeeper?**
A: "Zookeeper manages Kafka cluster metadata and coordinates broker state. In production, we'd use KRaft mode (Kafka's new built-in consensus), but Zookeeper is still widely used in existing deployments."

**Q: Why Docker Compose?**
A: "It provides infrastructure-as-code for the entire stack. Anyone can run `docker-compose up` and get identical environment, making development reproducible and collaboration easier."

**Q: Why did you start with just Kafka?**
A: "I validated each layer before adding complexity. This made debugging easier and helped me understand dependencies between services."

---

## ⏭️ Next Steps (Day 3-4)

After completing Day 1-2:
1. Commit your changes to Git
2. Add PostgreSQL to docker-compose.yml
3. Add Redis to docker-compose.yml
4. Create database schema

---

**Time Budget: 1-2 hours total**

**Questions or stuck?** Document the issue and error message - we'll debug together!
