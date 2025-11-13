# Apache Flink Quick Reference

Essential commands and patterns for working with Apache Flink in your cryptocurrency analyzer project.

---

## 🚀 Flink CLI Commands

### **Job Management**

```powershell
# List all running jobs
docker exec flink-jobmanager flink list

# List all jobs (including completed)
docker exec flink-jobmanager flink list --all

# Submit a job from JAR file
docker exec flink-jobmanager flink run /path/to/your-job.jar

# Submit with specific parallelism
docker exec flink-jobmanager flink run -p 4 /path/to/your-job.jar

# Cancel a running job
docker exec flink-jobmanager flink cancel <JOB_ID>

# Stop a job with savepoint
docker exec flink-jobmanager flink stop <JOB_ID>
```

### **Savepoint Management**

```powershell
# Create a savepoint
docker exec flink-jobmanager flink savepoint <JOB_ID>

# Create savepoint to specific directory
docker exec flink-jobmanager flink savepoint <JOB_ID> /opt/flink/data/savepoints

# Resume from savepoint
docker exec flink-jobmanager flink run -s /path/to/savepoint /path/to/job.jar
```

---

## 🌐 Flink Web UI Access

**URL:** http://localhost:8082

### **Main Sections:**

1. **Overview** - Cluster status at a glance
2. **Running Jobs** - Active streaming jobs
3. **Completed Jobs** - Historical job runs
4. **Task Managers** - Worker node status
5. **Job Manager** - Coordinator logs and config
6. **Submit New Job** - Upload and run JAR files

---

## 📊 Monitoring Commands

### **Check Cluster Health**

```powershell
# JobManager logs
docker-compose logs jobmanager | Select-Object -Last 50

# TaskManager logs
docker-compose logs taskmanager | Select-Object -Last 50

# Follow logs in real-time
docker-compose logs -f jobmanager
docker-compose logs -f taskmanager
```

### **Check Resource Usage**

```powershell
# Container stats
docker stats flink-jobmanager flink-taskmanager

# Memory usage
docker exec flink-jobmanager free -h

# Disk usage
docker exec flink-jobmanager df -h
```

---

## 🧪 Testing Flink Setup

### **Run Built-in Examples**

```powershell
# Word Count (streaming)
docker exec flink-jobmanager flink run /opt/flink/examples/streaming/WordCount.jar

# Socket Window Word Count (requires input)
docker exec flink-jobmanager flink run /opt/flink/examples/streaming/SocketWindowWordCount.jar --port 9999

# Top Speed Windowing
docker exec flink-jobmanager flink run /opt/flink/examples/streaming/TopSpeedWindowing.jar
```

### **Verify Task Slots**

```powershell
# Check available slots via REST API
curl http://localhost:8082/taskmanagers
```

---

## 🔧 Configuration Files

### **Main Config: `configs/flink-conf.yaml`**

Key settings you configured:

```yaml
# Parallelism
parallelism.default: 2
taskmanager.numberOfTaskSlots: 2

# State Backend
state.backend: rocksdb
state.backend.incremental: true

# Checkpointing
execution.checkpointing.interval: 60000
execution.checkpointing.mode: EXACTLY_ONCE

# Restart Strategy
restart-strategy: exponential-delay
```

---

## 🐛 Common Issues & Solutions

### **Issue: TaskManager not connecting**

```powershell
# Check network connectivity
docker exec taskmanager ping jobmanager

# Restart TaskManager
docker-compose restart taskmanager

# Check JobManager RPC port
docker exec jobmanager netstat -tlnp | grep 6123
```

### **Issue: Out of Memory**

```yaml
# In docker-compose.yml, increase memory:
jobmanager:
  environment:
    - |
      FLINK_PROPERTIES=
      jobmanager.memory.process.size: 2048m
```

### **Issue: Job submission fails**

```powershell
# Check JobManager logs for errors
docker-compose logs jobmanager | Select-String -Pattern "ERROR"

# Verify JAR file permissions
docker exec jobmanager ls -l /path/to/jar

# Check if job is already running
docker exec jobmanager flink list
```

---

## 📦 Building Custom Flink Jobs

### **Project Structure (for Week 4)**

```
src/
└── flink_jobs/
    ├── pom.xml (Maven) or build.gradle (Gradle)
    ├── CryptoPriceAggregator.java
    ├── MovingAverageCalculator.java
    └── TrendDetector.java
```

### **Maven Dependencies (Example)**

```xml
<dependencies>
    <!-- Flink Core -->
    <dependency>
        <groupId>org.apache.flink</groupId>
        <artifactId>flink-streaming-java</artifactId>
        <version>1.18.0</version>
    </dependency>
    
    <!-- Kafka Connector -->
    <dependency>
        <groupId>org.apache.flink</groupId>
        <artifactId>flink-connector-kafka</artifactId>
        <version>3.0.0-1.18</version>
    </dependency>
    
    <!-- JDBC Connector (PostgreSQL) -->
    <dependency>
        <groupId>org.apache.flink</groupId>
        <artifactId>flink-connector-jdbc</artifactId>
        <version>3.1.0-1.17</version>
    </dependency>
</dependencies>
```

### **Build JAR**

```bash
# Using Maven
mvn clean package

# Using Gradle
gradle clean build

# JAR will be in target/ or build/libs/
```

### **Deploy to Flink**

```powershell
# Copy JAR to JobManager container
docker cp target/crypto-analyzer.jar flink-jobmanager:/opt/flink/

# Submit job
docker exec flink-jobmanager flink run /opt/flink/crypto-analyzer.jar
```

---

## 🎯 Flink Job Patterns for Crypto Analysis

### **1. Simple Price Aggregation**

```java
DataStream<PriceUpdate> priceStream = env
    .addSource(new FlinkKafkaConsumer<>("crypto-prices", ...))
    .keyBy(price -> price.getCryptoId())
    .window(TumblingEventTimeWindows.of(Time.minutes(1)))
    .aggregate(new AverageAggregator());
```

### **2. Moving Average (Stateful)**

```java
DataStream<MovingAverage> movingAvg = priceStream
    .keyBy(price -> price.getCryptoId())
    .flatMap(new MovingAverageFunction(windowSize = 10));
```

### **3. Trend Detection**

```java
DataStream<Trend> trends = priceStream
    .keyBy(price -> price.getCryptoId())
    .process(new TrendDetectionFunction(threshold = 0.05));
```

---

## 📈 Performance Tuning

### **Increase Parallelism**

```powershell
# Submit with custom parallelism
docker exec flink-jobmanager flink run -p 4 /path/to/job.jar
```

### **Checkpoint Tuning**

```yaml
# In flink-conf.yaml
execution.checkpointing.interval: 30000  # More frequent (30s)
execution.checkpointing.timeout: 300000  # 5 minutes
```

### **Add More TaskManagers**

```yaml
# In docker-compose.yml
taskmanager:
  scale: 2  # Run 2 TaskManager instances
```

---

## 🔗 Useful REST API Endpoints

```powershell
# Cluster overview
curl http://localhost:8082/overview

# All jobs
curl http://localhost:8082/jobs

# Specific job details
curl http://localhost:8082/jobs/<JOB_ID>

# Task managers
curl http://localhost:8082/taskmanagers

# Job manager config
curl http://localhost:8082/jobmanager/config
```

---

## 📚 Additional Resources

- [Flink Documentation](https://nightlies.apache.org/flink/flink-docs-release-1.18/)
- [Flink Training](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/learn-flink/overview/)
- [Kafka Connector Guide](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/connectors/datastream/kafka/)
- [JDBC Connector Guide](https://nightlies.apache.org/flink/flink-docs-release-1.18/docs/connectors/datastream/jdbc/)

---

## 💡 Pro Tips

1. **Always use event time for financial data** - More accurate than processing time
2. **Set appropriate watermarks** - Handle network delays (10-30 seconds typical)
3. **Enable checkpointing** - Essential for production reliability
4. **Monitor backpressure** - Check in Flink Web UI Running Jobs section
5. **Use keyed state for per-crypto metrics** - Efficient and scalable

---

**Keep this file handy when building Flink jobs in Week 4!** 🚀
