# Quick Start Guide - Complete Stack

## 🚀 Launch Your Complete Streaming Infrastructure

One command to rule them all!

---

## 📋 Pre-Flight Checklist

Before starting, ensure:
- [ ] Docker Desktop is running
- [ ] No other services using ports: 2181, 5433, 6379, 8081, 8082, 9092
- [ ] At least 8GB RAM available for Docker
- [ ] At least 10GB disk space free

---

## 🎬 Start Everything

```powershell
cd C:\Real-Time-Cryptocurrency-Market-Analyzer

# Stop any existing containers
docker-compose down

# Start all 8 services
docker-compose up -d

# Wait for initialization (60 seconds)
timeout /t 60

# Check all containers
docker-compose ps
```

**Expected Output: 8 containers, all "Up" or "Up (healthy)"**

---

## ✅ Verify Each Service

### **1. Kafka (Ports 9092, 29092)**
```powershell
# Check broker
docker-compose logs kafka | Select-String -Pattern "started"

# Access UI
start http://localhost:8081
```

### **2. PostgreSQL (Port 5433)**
```powershell
# Verify database
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT * FROM cryptocurrencies;"

# Access pgAdmin
start http://localhost:5050
# Login: admin@crypto.com / admin
```

### **3. Redis (Port 6379)**
```powershell
# Test connection
docker exec redis redis-cli PING
# Should return: PONG
```

### **4. Flink (Port 8082)**
```powershell
# Check JobManager
docker-compose logs jobmanager | Select-String -Pattern "Started"

# Check TaskManager connection
docker-compose logs taskmanager | Select-String -Pattern "Successful"

# Access Web UI
start http://localhost:8082
```

---

## 🌐 Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Kafka UI | http://localhost:8081 | None |
| Flink Web UI | http://localhost:8082 | None |
| pgAdmin | http://localhost:5050 | admin@crypto.com / admin |
| PostgreSQL | localhost:5433 | crypto_user / crypto_pass |
| Redis | localhost:6379 | None |

---

## 🧪 Quick Health Check

Run this PowerShell script:

```powershell
# Quick health check script
Write-Host "=== Cryptocurrency Analyzer Health Check ===" -ForegroundColor Cyan

# Check all containers
Write-Host "`nContainer Status:" -ForegroundColor Yellow
docker-compose ps

# Check Kafka
Write-Host "`nKafka Status:" -ForegroundColor Yellow
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092 2>&1 | Select-String -Pattern "ApiVersion" | Select-Object -First 1

# Check PostgreSQL
Write-Host "`nPostgreSQL Status:" -ForegroundColor Yellow
docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT version();" 2>&1 | Select-String -Pattern "PostgreSQL"

# Check Redis
Write-Host "`nRedis Status:" -ForegroundColor Yellow
docker exec redis redis-cli PING

# Check Flink
Write-Host "`nFlink Status:" -ForegroundColor Yellow
docker exec flink-jobmanager flink list 2>&1 | Select-String -Pattern "No running jobs"

Write-Host "`n=== All Systems Operational ===" -ForegroundColor Green
```

---

## 🛑 Stop Everything

```powershell
# Graceful shutdown (keeps data)
docker-compose stop

# Full shutdown (keeps data)
docker-compose down

# Nuclear option (deletes all data - use carefully!)
docker-compose down -v
```

---

## 📊 Resource Usage

Expected resource consumption:

| Service | Memory | CPU | Notes |
|---------|--------|-----|-------|
| Kafka | ~500MB | 5-10% | Spikes during high throughput |
| PostgreSQL | ~200MB | 5% | Increases with data volume |
| Redis | ~50MB | <5% | Minimal overhead |
| Flink JobManager | ~1.6GB | 5% | Coordination overhead |
| Flink TaskManager | ~1.7GB | Varies | Depends on job complexity |
| Zookeeper | ~100MB | <5% | Metadata management |
| Kafka UI | ~200MB | <5% | Web interface |
| pgAdmin | ~200MB | <5% | Web interface |
| **Total** | **~4.5GB** | **~30-40%** | 8 containers |

---

## 🔄 Restart Individual Services

```powershell
# Restart specific service
docker-compose restart kafka
docker-compose restart postgres
docker-compose restart jobmanager
docker-compose restart taskmanager

# View logs
docker-compose logs -f <service-name>
```

---

## 🐛 Common Startup Issues

### **Issue: Port already in use**

```powershell
# Find what's using the port
netstat -ano | findstr :8082

# Kill process (replace PID)
taskkill /PID <PID> /F
```

### **Issue: Container keeps restarting**

```powershell
# Check logs for specific container
docker-compose logs <container-name>

# Common fixes:
# 1. Increase Docker memory (Settings → Resources)
# 2. Wait longer for dependencies
# 3. Check port conflicts
```

### **Issue: Out of disk space**

```powershell
# Clean up Docker
docker system prune -a

# Remove old volumes (WARNING: deletes data)
docker volume prune
```

---

## 📈 Performance Tuning

### **For Development (Lower Resources)**

```yaml
# In docker-compose.yml, reduce memory:
jobmanager:
  environment:
    - jobmanager.memory.process.size: 1024m  # Reduced from 1600m

taskmanager:
  environment:
    - taskmanager.memory.process.size: 1024m  # Reduced from 1728m
```

### **For Production Testing (Higher Performance)**

```yaml
# Increase resources:
jobmanager:
  environment:
    - jobmanager.memory.process.size: 2048m

taskmanager:
  environment:
    - taskmanager.memory.process.size: 2048m
  scale: 2  # Run 2 TaskManagers
```

---

## 💾 Backup & Restore

### **Backup Everything**

```powershell
# Backup PostgreSQL
docker exec postgres pg_dump -U crypto_user crypto_db > backup_$(Get-Date -Format "yyyyMMdd_HHmmss").sql

# Backup Redis
docker exec redis redis-cli SAVE
docker cp redis:/data/dump.rdb redis_backup_$(Get-Date -Format "yyyyMMdd_HHmmss").rdb
```

### **Restore from Backup**

```powershell
# Restore PostgreSQL
docker exec -i postgres psql -U crypto_user crypto_db < backup_20250111_120000.sql

# Restore Redis
docker cp redis_backup_20250111_120000.rdb redis:/data/dump.rdb
docker-compose restart redis
```

---

## 🎯 Next Steps After Startup

1. **Verify Kafka**: Create topic, produce message
2. **Verify PostgreSQL**: Check tables and views
3. **Verify Redis**: Test PING/SET/GET
4. **Verify Flink**: Check task slots in Web UI

See individual phase documentation for detailed verification steps!

---

## 📞 Quick Reference

```powershell
# Start
docker-compose up -d

# Stop
docker-compose down

# Logs
docker-compose logs -f

# Status
docker-compose ps

# Restart
docker-compose restart

# Clean start
docker-compose down -v && docker-compose up -d
```

---

**Your complete streaming infrastructure in one command!** 🚀
