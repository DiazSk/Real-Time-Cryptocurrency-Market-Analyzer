# Local Testing Guide & Troubleshooting

This guide addresses common issues when running the Real-Time Cryptocurrency Market Analyzer locally.

## System Requirements

- **RAM**: 8-16GB minimum (10GB+ recommended)
- **Docker Desktop**: Allocate at least 6GB to Docker
- **Disk**: 10GB free space for Docker volumes

## Quick Start

```bash
bash scripts/start_pipeline.sh   # docker-compose up -d + health checks + starts the producer

make build-flink                 # Compile the Flink job (requires Maven + Java 11/17)
make deploy-flink                 # Copy the JAR and submit it

make api                          # Run the FastAPI backend
cd frontend && npm install && npm run dev   # Run the Next.js terminal

make help                         # Show all available make targets
```

### Manual Docker Commands

```bash
docker-compose up -d
```

---

## Common Issues & Solutions

### 1. Resource Starvation (OOM / Containers Crashing)

**Symptoms:**

- Containers exit unexpectedly
- `docker ps` shows containers restarting
- Flink JobManager hangs during deployment

**Solutions:**

1. **Increase Docker memory allocation:**
   - Open Docker Desktop → Settings → Resources
   - Set Memory to at least 6GB (8GB recommended)

2. **Stop unnecessary applications** before running

3. **Monitor resource usage:**
   ```bash
   docker stats
   ```

---

### 2. Hardcoded Credentials Issues

**Problem:** Java Flink jobs had hardcoded credentials that required recompilation when changed.

**Solution:** Credentials are now read from environment variables. Configure via `.env` file:

1. Copy the example file:

   ```bash
   cp .env.example .env    # Linux/macOS
   copy .env.example .env  # Windows
   ```

2. Edit `.env` with your custom values:

   ```dotenv
   POSTGRES_USER=your_custom_user
   POSTGRES_PASSWORD=your_secure_password
   POSTGRES_DB=your_database_name
   ```

3. The Java jobs and Docker containers will automatically use these values.

**No recompilation needed** when changing credentials!

---

### 3. Startup Race Conditions (Services Not Ready)

**Symptoms:**

- Flink job fails to connect to Kafka
- "Connection refused" errors
- Producer can't find Kafka topic

**Solutions:**

1. **Use the cross-platform health check script:**

   ```bash
   # Check all services
   venv/bin/python scripts/wait_for_services.py all

   # Check specific services
   venv/bin/python scripts/wait_for_services.py kafka postgres redis

   # With custom timeout
   venv/bin/python scripts/wait_for_services.py kafka --retries 60 --interval 3
   ```

2. **Using make (Linux/macOS/WSL):**

   ```bash
   make health
   ```

3. **Verify containers are healthy:**
   ```bash
   docker ps --format "table {{.Names}}\t{{.Status}}"
   ```
   Look for `(healthy)` in the status column.

---

### 4. Network / Localhost Confusion

**Understanding Docker networking:**

| Running From              | Kafka Address    | PostgreSQL Port  | Redis Port       |
| ------------------------- | ---------------- | ---------------- | ---------------- |
| Inside Docker (container) | `kafka:29092`    | `postgres:5432`  | `redis:6379`     |
| Outside Docker (your IDE) | `localhost:9092` | `localhost:5433` | `localhost:6379` |

**Common scenarios:**

1. **Python Producer from IDE:**
   - Uses `localhost:9092` (already configured)

2. **Flink job in Docker:**
   - Uses `kafka:29092` (already configured)

3. **Testing from command line:**

   ```bash
   # Test Kafka from host
   docker exec kafka kafka-topics --bootstrap-server localhost:9092 --list

   # Test PostgreSQL from host
   docker exec postgres psql -U crypto_user -d crypto_db -c "SELECT 1"

   # Test Redis from host
   docker exec redis redis-cli ping
   ```

---

### 5. Java/Maven Version Issues

**Problem:** Compiled JAR doesn't work with Flink cluster.

**Requirements:**

- Compile with Java 11 or 17 (match Flink image)
- Flink image uses: `flink:1.18-scala_2.12-java11`

**Check your Java version:**

```bash
java -version
```

**Fix version mismatch:**

1. Install JDK 11 or 17
2. Set JAVA_HOME:
   ```bash
   set JAVA_HOME=C:\path\to\jdk-11
   ```
3. Rebuild the JAR:
   ```bash
   cd src\flink_jobs
   mvn clean package -DskipTests
   ```

---

## Environment Variables Reference

All configuration can be customized via environment variables:

### Core Database Settings

| Variable            | Default                                  | Description       |
| ------------------- | ---------------------------------------- | ----------------- |
| `POSTGRES_DB`       | `crypto_db`                              | Database name     |
| `POSTGRES_USER`     | `crypto_user`                            | Database username |
| `POSTGRES_PASSWORD` | `crypto_pass`                            | Database password |
| `POSTGRES_HOST`     | `postgres` (docker) / `localhost` (host) | Database host     |
| `POSTGRES_PORT`     | `5432` (docker) / `5433` (host)          | Database port     |

### Kafka Settings

| Variable                  | Default         | Description          |
| ------------------------- | --------------- | -------------------- |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092`   | Kafka broker address |
| `KAFKA_TRADES_TOPIC`      | `crypto-trades` | Input topic name     |
| `KAFKA_ALERT_TOPIC`       | `crypto-alerts` | Alert topic name     |

### Redis Settings

| Variable     | Default | Description       |
| ------------ | ------- | ----------------- |
| `REDIS_HOST` | `redis` | Redis server host |
| `REDIS_PORT` | `6379`  | Redis server port |

---

## Service Ports Reference

| Service             | Port  | URL                   |
| ------------------- | ----- | --------------------- |
| Kafka (external)    | 9092  | `localhost:9092`      |
| Kafka (internal)    | 29092 | `kafka:29092`         |
| Kafka UI            | 8081  | http://localhost:8081 |
| PostgreSQL          | 5433  | `localhost:5433`      |
| Redis               | 6379  | `localhost:6379`      |
| Flink UI            | 8082  | http://localhost:8082 |
| FastAPI             | 8000  | http://localhost:8000 |
| Next.js terminal    | 3000  | http://localhost:3000 |
| pgAdmin             | 5050  | http://localhost:5050 |

---

## Troubleshooting Commands

### Check all container status

```bash
docker-compose ps
```

### View container logs

```bash
docker-compose logs -f kafka
```

### Restart a specific service

```bash
docker-compose restart kafka
```

### Full reset (removes all data)

```bash
docker-compose down -v
# Or: make clean
```

### Check Docker resource usage

```bash
docker stats --no-stream
```

### Check service health

```bash
venv/bin/python scripts/wait_for_services.py all
# Or: make health
```

---

## Getting Help

1. Check the logs: `docker-compose logs -f [service_name]`
2. Verify healthchecks: `venv/bin/python scripts/wait_for_services.py all`
3. Review this guide for common issues
