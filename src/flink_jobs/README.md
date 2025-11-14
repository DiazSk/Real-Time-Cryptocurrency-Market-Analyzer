# Crypto Analyzer - Flink Jobs

Apache Flink streaming jobs for real-time cryptocurrency market analysis.

---

## 📋 Project Structure

```
src/flink_jobs/
├── pom.xml                          # Maven project configuration
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/crypto/analyzer/
│   │   │       ├── CryptoPriceAggregator.java    # Main Flink job
│   │   │       └── models/
│   │   │           └── PriceUpdate.java          # Price data model
│   │   └── resources/
│   │       └── log4j2.properties                 # Logging configuration
│   └── test/
│       └── java/                                 # Unit tests (coming soon)
├── target/                                       # Build output (generated)
└── README.md                                     # This file
```

---

## 🚀 Quick Start

### **Prerequisites**
- ✅ Java 21 installed (verify: `java -version`)
- ✅ Maven 3.9+ installed (verify: `mvn -version`)
- ✅ Docker containers running (Kafka, Flink, PostgreSQL, Redis)

### **Build the Project**

```bash
# Navigate to flink_jobs directory
cd C:\Real-Time-Cryptocurrency-Market-Analyzer\src\flink_jobs

# Clean and build
mvn clean package

# Output: target/crypto-analyzer-flink-1.0.0.jar
```

**Build time:** ~30-60 seconds (first time downloads dependencies)

### **Submit Job to Flink Cluster**

```bash
# Copy JAR to Flink JobManager container
docker cp target/crypto-analyzer-flink-1.0.0.jar flink-jobmanager:/opt/flink/

# Submit the job
docker exec flink-jobmanager flink run /opt/flink/crypto-analyzer-flink-1.0.0.jar

# Check job status in Flink Web UI: http://localhost:8082
```

### **View Job Output**

```bash
# View TaskManager logs (where print() outputs appear)
docker logs -f flink-taskmanager

# Should see price updates streaming:
# PriceUpdate{symbol='BTC', price=45000.00, ...}
# PriceUpdate{symbol='ETH', price=3200.50, ...}
```

---

## 🏗️ Maven Dependencies

### **Core Flink Dependencies**
- `flink-streaming-java` (1.18.1) - Flink streaming API
- `flink-clients` (1.18.1) - Client libraries

### **Connectors**
- `flink-connector-kafka` (3.0.2-1.18) - Kafka source/sink
- `flink-connector-jdbc` (3.1.2-1.18) - PostgreSQL sink (Week 7)
- `jedis` (5.1.2) - Redis client (Week 7)

### **Data Processing**
- `jackson-databind` (2.17.0) - JSON serialization
- `postgresql` (42.7.3) - PostgreSQL JDBC driver

---

## 📝 Current Implementation (Phase 3 - Week 5)

### **What It Does:**
1. ✅ Connects to Kafka topic `crypto-prices`
2. ✅ Deserializes JSON messages to `PriceUpdate` POJOs
3. ✅ Filters invalid messages
4. ✅ Prints price updates to console

### **Configuration:**
- **Kafka Bootstrap Servers:** `kafka:29092` (Docker internal)
- **Kafka Topic:** `crypto-prices`
- **Consumer Group:** `flink-crypto-analyzer`
- **Parallelism:** 2 (matches TaskManager slots)
- **Checkpointing:** Enabled (60s interval from `flink-conf.yaml`)

### **Data Flow:**

```
Python Producer (CoinGecko API)
        ↓
Kafka Topic: crypto-prices
        ↓
Flink Kafka Source
        ↓
Deserialize JSON → PriceUpdate POJO
        ↓
Filter (isValid)
        ↓
Print to Console
```

---

## 🔧 Maven Commands

```bash
# Clean build artifacts
mvn clean

# Compile only
mvn compile

# Run tests (when added)
mvn test

# Build JAR (without tests)
mvn package -DskipTests

# Build and install to local Maven repo
mvn install

# View dependency tree
mvn dependency:tree

# Download all dependencies
mvn dependency:resolve
```

---

## 🎯 Coming Next (Phase 3 Continuation)

### **Week 5 - Kafka Integration & Windowing**
- ✅ Basic Kafka consumption (DONE)
- ⏭️ Event-time watermarks (10-second delay)
- ⏭️ 1-minute tumbling windows
- ⏭️ OHLC aggregation function

### **Week 6 - Multi-Window Processing**
- ⏭️ 5-minute and 15-minute windows
- ⏭️ Price change percentage calculations
- ⏭️ Anomaly detection (5% spike alerts)
- ⏭️ Write alerts to `crypto-alerts` Kafka topic

### **Week 7 - Database Integration**
- ⏭️ PostgreSQL JDBC sink for aggregations
- ⏭️ Redis sink for latest prices
- ⏭️ Batch insert optimization
- ⏭️ Exactly-once semantics validation

---

## 🐛 Troubleshooting

### **Problem: Maven build fails with "package org.apache.flink does not exist"**

```bash
# Solution: Force re-download dependencies
mvn clean install -U
```

### **Problem: Cannot connect to Kafka from Flink**

```bash
# Check Kafka is accessible from Flink container
docker exec flink-jobmanager ping kafka

# Verify Kafka topic exists
docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

# Check if Python producer is running
docker logs kafka | grep crypto-prices
```

### **Problem: Job fails immediately after submission**

```bash
# Check JobManager logs for errors
docker logs flink-jobmanager | grep ERROR

# Common issues:
# - Wrong Kafka bootstrap server (use kafka:29092 not localhost:9092)
# - Kafka topic doesn't exist
# - Serialization errors (Jackson version mismatch)
```

### **Problem: No output in TaskManager logs**

```bash
# Ensure Python producer is sending messages
# In separate terminal:
cd C:\Real-Time-Cryptocurrency-Market-Analyzer
python src/producers/crypto_price_producer.py

# Wait 10-20 seconds, then check TaskManager logs again
docker logs -f flink-taskmanager
```

---

## 📊 Verifying Job is Running

### **Via Flink Web UI (Recommended)**
1. Open http://localhost:8082
2. Go to **Running Jobs** tab
3. Click on job name
4. Check:
   - Status: `RUNNING`
   - Tasks: 2/2 (both task slots active)
   - Records Received: Increasing count
   - Backpressure: None (green)

### **Via Command Line**

```bash
# List running jobs
docker exec flink-jobmanager flink list

# Output:
# ------------------- Running/Restarting Jobs -------------------
# 12.11.2025 10:30:00 : <job-id> : Crypto Price Aggregator (RUNNING)
```

---

## 🎓 Interview Talking Points

### **Why Flink over Spark Streaming?**

> "I chose Apache Flink for true stream processing with event-time semantics and low latency. Unlike Spark Streaming's micro-batch approach, Flink processes each event immediately, which is critical for financial data where delays can impact trading decisions. Flink's watermark mechanism also handles out-of-order events elegantly, ensuring accurate windowed aggregations even with network delays."

### **Maven Shade Plugin Configuration**

> "The Maven Shade Plugin creates a fat JAR that bundles all dependencies except those provided by Flink runtime. This is crucial because Flink's cluster already has core libraries, and including them would cause classpath conflicts. The plugin also relocates conflicting packages and merges service files automatically."

### **Exactly-Once Semantics**

> "I configured Flink with exactly-once processing mode and 60-second checkpointing. This means if a TaskManager fails, Flink restarts from the last successful checkpoint, replaying only the messages that weren't fully processed. Combined with Kafka's transactional producer and PostgreSQL's JDBC exactly-once sink, I guarantee no duplicate or lost aggregations."

---

## 📚 Resources

- [Flink Documentation](https://nightlies.apache.org/flink/flink-docs-release-1.18/)
- [Kafka Connector Guide](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/connectors/datastream/kafka/)
- [Maven Shade Plugin](https://maven.apache.org/plugins/maven-shade-plugin/)
- [Jackson JSON Library](https://github.com/FasterXML/jackson)

---

## ✅ Success Criteria for Week 5

- [x] Maven project builds successfully
- [x] Fat JAR created in `target/` directory
- [x] Job submits to Flink without errors
- [ ] Price updates appear in TaskManager logs
- [ ] Flink Web UI shows job running
- [ ] Can stop and restart job without data loss

---

**Built with ☕ and 💪 for FAANG-level streaming infrastructure**

*Last Updated: Phase 3, Week 5, Day 1-2*
