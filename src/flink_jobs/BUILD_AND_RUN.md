# Build and Run Guide - Flink Jobs

Step-by-step instructions to build and deploy your Flink streaming job.

---

## ✅ Prerequisites Checklist

Before building, ensure:
- [ ] Java 21 installed: `java -version`
- [ ] Maven installed: `mvn -version`
- [ ] Docker containers running: `docker-compose ps`
- [ ] Python producer sending data to Kafka
- [ ] Kafka topic `crypto-prices` exists

---

## 🔨 Step 1: Build the JAR

```bash
# Navigate to flink_jobs directory
cd C:\Real-Time-Cryptocurrency-Market-Analyzer\src\flink_jobs

# Clean any previous builds
mvn clean

# Build the fat JAR (includes all dependencies)
mvn package

# Expected output:
# [INFO] BUILD SUCCESS
# [INFO] Total time: 45 s
# [INFO] Finished at: 2025-11-13T10:30:00-08:00
```

**Output location:** `target/crypto-analyzer-flink-1.0.0.jar`

### **Troubleshooting Build Issues:**

**Problem: `mvn: command not found`**
```bash
# Check if Maven is in PATH
echo $PATH | grep -i maven

# If not, add Maven to PATH:
export PATH=$PATH:/c/Maven/apache-maven-3.9.9/bin  # Adjust path
```

**Problem: Build fails with compilation errors**
```bash
# Ensure Java 21 is being used
mvn -version

# Force re-download dependencies
mvn clean install -U
```

**Problem: Tests fail**
```bash
# Skip tests for now (we'll add them later)
mvn package -DskipTests
```

---

## 🚢 Step 2: Copy JAR to Flink Container

```bash
# From flink_jobs directory
docker cp target/crypto-analyzer-flink-1.0.0.jar flink-jobmanager:/opt/flink/

# Verify the file is copied
docker exec flink-jobmanager ls -lh /opt/flink/crypto-analyzer-flink-1.0.0.jar
```

**Expected output:**
```
-rw-r--r-- 1 flink flink 15M Nov 13 10:35 /opt/flink/crypto-analyzer-flink-1.0.0.jar
```

---

## 🚀 Step 3: Submit Job to Flink Cluster

### **Option A: Via Command Line (Recommended for First Run)**

```bash
# Submit the job
docker exec flink-jobmanager flink run /opt/flink/crypto-analyzer-flink-1.0.0.jar

# Expected output:
# Job has been submitted with JobID <job-id>
# Job is running...
```

### **Option B: Via Flink Web UI**

1. Open http://localhost:8082
2. Click **Submit New Job** tab
3. Click **+ Add New**
4. Select `/opt/flink/crypto-analyzer-flink-1.0.0.jar`
5. Click **Submit**

---

## 👀 Step 4: Verify Job is Running

### **Check Job Status:**

```bash
# List running jobs
docker exec flink-jobmanager flink list

# Expected output:
# ------------------- Running/Restarting Jobs -------------------
# 13.11.2025 10:35:00 : <job-id> : Crypto Price Aggregator - Phase 3 Week 5 (RUNNING)
```

### **Check Flink Web UI:**

1. Open http://localhost:8082
2. Navigate to **Running Jobs**
3. You should see: **Crypto Price Aggregator - Phase 3 Week 5**
4. Click on the job to see:
   - Operator graph
   - Task metrics
   - Checkpoints
   - Backpressure

---

## 📊 Step 5: View Output

### **Watch TaskManager Logs (Live):**

```bash
# Follow logs in real-time
docker logs -f flink-taskmanager

# Expected output (every 10 seconds):
# 2025-11-13 10:36:12,345 INFO  PriceUpdate{symbol='BTC', price=45234.50, volume24h=28500000000, ...}
# 2025-11-13 10:36:22,456 INFO  PriceUpdate{symbol='ETH', price=3189.75, volume24h=15200000000, ...}
# 2025-11-13 10:36:32,567 INFO  PriceUpdate{symbol='BTC', price=45256.00, volume24h=28510000000, ...}
```

### **View Recent Logs (Last 50 Lines):**

```bash
docker logs --tail=50 flink-taskmanager
```

### **Search for Specific Symbol:**

```bash
# Filter for Bitcoin prices only
docker logs flink-taskmanager | grep "BTC"

# Filter for Ethereum prices only
docker logs flink-taskmanager | grep "ETH"
```

---

## 🛑 Step 6: Stop the Job

### **Option A: Cancel Job (Clean Shutdown)**

```bash
# Get job ID
docker exec flink-jobmanager flink list

# Cancel with savepoint (recommended)
docker exec flink-jobmanager flink cancel -s /opt/flink/data/savepoints <JOB_ID>

# Cancel without savepoint
docker exec flink-jobmanager flink cancel <JOB_ID>
```

### **Option B: Via Flink Web UI**

1. Go to **Running Jobs**
2. Click on your job
3. Click **Cancel Job** button (top right)

---

## 🔄 Step 7: Redeploy After Code Changes

```bash
# 1. Stop running job
docker exec flink-jobmanager flink cancel <JOB_ID>

# 2. Rebuild JAR
cd C:\Real-Time-Cryptocurrency-Market-Analyzer\src\flink_jobs
mvn clean package -DskipTests

# 3. Copy new JAR
docker cp target/crypto-analyzer-flink-1.0.0.jar flink-jobmanager:/opt/flink/

# 4. Resubmit job
docker exec flink-jobmanager flink run /opt/flink/crypto-analyzer-flink-1.0.0.jar
```

---

## 🎯 Success Criteria

✅ **You've succeeded when:**

1. Maven build completes with `BUILD SUCCESS`
2. JAR file exists: `target/crypto-analyzer-flink-1.0.0.jar`
3. Job appears in Flink Web UI under **Running Jobs**
4. TaskManager logs show price updates every 10 seconds
5. No errors in JobManager or TaskManager logs
6. Flink Web UI shows:
   - Records Received: > 0 (increasing)
   - Records Sent: > 0 (increasing)
   - Backpressure: None (green)

---

## 🐛 Common Issues

### **Issue: No output in TaskManager logs**

**Cause:** Python producer not running or Kafka topic empty

**Solution:**
```bash
# Start Python producer
cd C:\Real-Time-Cryptocurrency-Market-Analyzer
python src/producers/crypto_price_producer.py

# Verify messages in Kafka
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic crypto-prices --from-beginning --max-messages 5
```

---

### **Issue: Job fails immediately**

**Cause:** Cannot connect to Kafka

**Solution:**
```bash
# Check Kafka is reachable from Flink
docker exec flink-jobmanager ping kafka

# Verify Kafka bootstrap server
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# Check if topic exists
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list | grep crypto
```

---

### **Issue: Serialization errors**

**Cause:** JSON structure mismatch

**Solution:**
```bash
# Check Python producer JSON format
docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic crypto-prices --from-beginning --max-messages 1

# Ensure it matches PriceUpdate.java fields:
# - symbol (String)
# - price (number)
# - volume_24h (number)
# - market_cap (number)
# - price_change_24h (number)
# - timestamp (number)
# - source (String)
```

---

## 📸 Portfolio Screenshots to Capture

1. ✅ Maven build success terminal output
2. ✅ Flink Web UI showing running job
3. ✅ TaskManager logs with price updates
4. ✅ Job metrics (Records Received/Sent)
5. ✅ Task distribution across TaskManager slots

---

## ⏭️ Next Steps

After verifying basic Kafka consumption works:

**Week 5, Day 3-4:** Add event-time watermarks
**Week 5, Day 5-7:** Implement 1-minute tumbling windows for OHLC
**Week 6:** Multi-window processing and anomaly detection
**Week 7:** PostgreSQL and Redis sinks

---

**You're now running production-grade stream processing, bhau!** 🚀💪

*Keep this guide handy for the rest of Phase 3!*
