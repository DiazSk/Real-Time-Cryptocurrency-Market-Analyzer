# PostgreSQL/TimescaleDB Setup - Troubleshooting & Fixes

## Issue Summary

During Phase 2, Day 3-4 setup, the PostgreSQL container was crashing on startup. This document details the root causes and fixes applied.

---

## 🔴 Root Causes Identified

### **1. Wrong Docker Image**

**Problem:**
```yaml
# Original (INCORRECT)
postgres:
  image: postgres:15-alpine
```

**Issue:**
- The `init-db.sql` schema requires TimescaleDB extension
- Plain PostgreSQL doesn't include TimescaleDB
- Container crashed when trying to `CREATE EXTENSION IF NOT EXISTS "timescaledb"`

**Fix:**
```yaml
# Corrected
postgres:
  image: timescale/timescaledb:latest-pg15
```

**Why this matters:**
TimescaleDB is specifically designed for time-series data (like cryptocurrency prices). It provides:
- Automatic data partitioning by time
- Optimized time-based queries (10-100x faster)
- Built-in time-series functions
- Efficient compression for historical data

---

### **2. Invalid Primary Key for Hypertable**

**Problem:**
```sql
-- Original (INCORRECT)
CREATE TABLE raw_price_data (
    id BIGSERIAL PRIMARY KEY,
    ...
    timestamp TIMESTAMP NOT NULL
);

SELECT create_hypertable('raw_price_data', 'timestamp');
```

**Issue:**
TimescaleDB hypertables require the partitioning column (`timestamp`) to be part of the primary key. Error received:
```
ERROR: cannot create a unique index without the column "timestamp"
```

**Fix:**
```sql
-- Corrected
CREATE TABLE raw_price_data (
    id BIGSERIAL,
    ...
    timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (id, timestamp)  -- Composite key
);

SELECT create_hypertable('raw_price_data', 'timestamp');
```

**Why this matters:**
- TimescaleDB partitions data by time ranges (chunks)
- Each chunk needs unique identification
- Composite key ensures uniqueness within each time partition
- This is a **production best practice** for time-series databases

---

### **3. Port Conflict**

**Problem:**
```yaml
# Original
postgres:
  ports:
    - "5432:5432"
```

**Issue:**
Port 5432 was already in use on the host machine (likely another PostgreSQL instance or previous container).

**Fix:**
```yaml
# Corrected
postgres:
  ports:
    - "5433:5432"  # External port 5433, internal still 5432
```

**Why this matters:**
- Docker port mapping format: `HOST_PORT:CONTAINER_PORT`
- Container still uses standard 5432 internally
- Host accesses via 5433 to avoid conflicts
- Other containers still connect to `postgres:5432` (internal network)

---

## ✅ Final Working Configuration

### **docker-compose.yml**
```yaml
postgres:
  image: timescale/timescaledb:latest-pg15  # Changed from postgres:15-alpine
  container_name: postgres
  environment:
    POSTGRES_DB: crypto_db
    POSTGRES_USER: crypto_user
    POSTGRES_PASSWORD: crypto_pass
  ports:
    - "5433:5432"  # Changed from 5432:5432
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./configs/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
  networks:
    - crypto-network
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U crypto_user -d crypto_db"]
    interval: 10s
    timeout: 5s
    retries: 5
```

### **init-db.sql (Key Changes)**
```sql
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- Composite primary key for hypertable compatibility
CREATE TABLE IF NOT EXISTS raw_price_data (
    id BIGSERIAL,
    crypto_id INTEGER NOT NULL REFERENCES cryptocurrencies(id),
    price DECIMAL(20, 8) NOT NULL,
    volume_24h DECIMAL(20, 2),
    market_cap DECIMAL(20, 2),
    price_change_24h DECIMAL(10, 4),
    timestamp TIMESTAMP NOT NULL,
    kafka_offset BIGINT,
    kafka_partition INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, timestamp)  -- Composite key!
);

-- Create hypertable (now works!)
SELECT create_hypertable('raw_price_data', 'timestamp', if_not_exists => TRUE);
```

---

## 🎓 Key Learnings (Interview-Ready)

### **1. Time-Series Database Selection**

**Why TimescaleDB over plain PostgreSQL?**
> "For cryptocurrency price data, I chose TimescaleDB over plain PostgreSQL because it's specifically optimized for time-series workloads. It provides automatic time-based partitioning (hypertables), 10-100x faster time-range queries, and built-in compression. The composite primary key pattern ensures data integrity across time partitions while maintaining query performance."

### **2. Debugging Docker Container Issues**

**Process followed:**
1. Check container status: `docker-compose ps`
2. Examine logs: `docker-compose logs postgres`
3. Identify error: "extension timescaledb not found"
4. Research TimescaleDB requirements
5. Fix image + schema
6. Verify: `docker exec -it postgres psql -U crypto_user -d crypto_db`

**Interview talking point:**
> "When the PostgreSQL container crashed, I systematically debugged by examining logs, identifying the missing TimescaleDB extension, updating to the correct Docker image, and adjusting the schema for hypertable compatibility. This demonstrates my ability to troubleshoot distributed systems and understand the dependencies between components."

### **3. Composite Keys in Distributed Databases**

**Why composite primary key?**
> "TimescaleDB partitions data into chunks by time ranges. A composite key (id, timestamp) ensures uniqueness within each chunk, which is critical for distributed time-series databases. This pattern is used in production systems at companies like Uber and Airbnb for metrics storage."

---

## 📊 Verification Commands

After fixes applied, verify everything works:

```bash
# 1. Check all containers healthy
docker-compose ps

# 2. Verify TimescaleDB extension loaded
docker exec -it postgres psql -U crypto_user -d crypto_db -c "SELECT * FROM pg_extension WHERE extname='timescaledb';"

# 3. Verify hypertable created
docker exec -it postgres psql -U crypto_user -d crypto_db -c "\d+ raw_price_data"

# 4. Check initial data
docker exec -it postgres psql -U crypto_user -d crypto_db -c "SELECT * FROM cryptocurrencies;"

# 5. Test connection from host
psql -h localhost -p 5433 -U crypto_user -d crypto_db -c "SELECT version();"
```

---

## 🔄 If You Need to Start Fresh

If you need to completely reset:

```bash
# WARNING: This deletes all data!
docker-compose down -v

# Start fresh
docker-compose up -d

# Wait for initialization
sleep 30

# Verify
docker-compose ps
docker-compose logs postgres | grep "initialized"
```

---

## 📝 Documentation Updated

After these fixes, the following files were updated:
- ✅ `docker-compose.yml` - Changed to TimescaleDB image, port 5433
- ✅ `configs/init-db.sql` - Composite primary key, hypertable enabled
- ✅ `DATABASE_CONNECTIONS.md` - Updated all port references to 5433
- ✅ `PHASE2_DAY3-4.md` - Updated port and added TimescaleDB notes
- ✅ `README.md` - Updated tech stack and ports table

---

## 🎯 Production Considerations

For a production deployment, also consider:

1. **Connection Pooling**: Use PgBouncer for connection management
2. **Replication**: Set up streaming replication for high availability
3. **Backups**: Implement continuous WAL archiving
4. **Monitoring**: Add Prometheus + Grafana for metrics
5. **Security**: SSL/TLS encryption, IAM authentication
6. **Compression**: Enable TimescaleDB compression for older data
7. **Retention**: Automatic data retention policies for old chunks

---

## 💡 Related Resources

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [Hypertables Best Practices](https://docs.timescale.com/use-timescale/latest/hypertables/)
- [Time-Series Schema Design](https://docs.timescale.com/timescaledb/latest/how-to-guides/schema-management/)
- [PostgreSQL Composite Keys](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS)

---

**Issue Resolved:** All 6 services now running successfully with TimescaleDB-optimized time-series storage! 🎉
