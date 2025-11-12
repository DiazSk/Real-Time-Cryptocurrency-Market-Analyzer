# Database Connection Guide

Quick reference for connecting to PostgreSQL and Redis in your development environment.

---

## 🗃️ PostgreSQL Connections

### **Credentials**
```
Host: localhost (from your machine) OR postgres (from other containers)
Port: 5433
Database: crypto_db
Username: crypto_user
Password: crypto_pass
```

### **Connection Strings**

**Python (psycopg2):**
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="crypto_db",
    user="crypto_user",
    password="crypto_pass"
)
```

**Python (SQLAlchemy):**
```python
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://crypto_user:crypto_pass@localhost:5433/crypto_db"
)
```

**JDBC (Java/Flink):**
```
jdbc:postgresql://postgres:5433/crypto_db
```

### **Command Line Access**

```bash
# From host machine (if psql installed)
psql -h localhost -p 5433 -U crypto_user -d crypto_db

# From Docker container
docker exec -it postgres psql -U crypto_user -d crypto_db
```

---

## 🔴 Redis Connections

### **Credentials**
```
Host: localhost (from your machine) OR redis (from other containers)
Port: 6379
Password: (none - no password set)
```

### **Connection Strings**

**Python (redis-py):**
```python
import redis

r = redis.Redis(
    host='localhost',
    port=6379,
    decode_responses=True
)

# Test
r.set('test', 'hello')
print(r.get('test'))  # 'hello'
```

**Python (with connection pool):**
```python
import redis

pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    decode_responses=True
)
r = redis.Redis(connection_pool=pool)
```

### **Command Line Access**

```bash
# From Docker container
docker exec -it redis redis-cli

# Common commands:
PING              # Test connection
SET key value     # Set a key
GET key          # Get a value
KEYS *           # List all keys (use carefully!)
DEL key          # Delete a key
FLUSHALL         # Clear all data (dangerous!)
```

---

## 🌐 pgAdmin Access

**URL:** http://localhost:5050

**Login:**
- Email: admin@crypto.com
- Password: admin

**Server Configuration:**
- Name: Crypto DB (any name you want)
- Host: `postgres` (important: use container name!)
- Port: 5433
- Database: crypto_db
- Username: crypto_user
- Password: crypto_pass

---

## 📊 Useful Database Queries

### **Check Current State**

```sql
-- List all tables
\dt

-- Count records in each table
SELECT 
    'cryptocurrencies' as table_name, COUNT(*) as count FROM cryptocurrencies
UNION ALL
SELECT 'raw_price_data', COUNT(*) FROM raw_price_data
UNION ALL
SELECT 'price_aggregates_1m', COUNT(*) FROM price_aggregates_1m;

-- Check database size
SELECT pg_size_pretty(pg_database_size('crypto_db'));
```

### **View Latest Data**

```sql
-- Latest prices
SELECT * FROM v_latest_prices;

-- Last 10 price updates for Bitcoin
SELECT * FROM raw_price_data 
WHERE crypto_id = 1 
ORDER BY timestamp DESC 
LIMIT 10;

-- 24-hour statistics
SELECT * FROM v_price_stats_24h;
```

### **Monitoring Queries**

```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity;

-- Table sizes
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

---

## 🔴 Useful Redis Commands

### **Basic Operations**

```bash
# Set with expiration (60 seconds)
SETEX btc_price 60 "45000.50"

# Get with TTL check
GET btc_price
TTL btc_price

# Store JSON (as string)
SET crypto:btc:latest '{"price":45000,"time":"2025-01-11T10:00:00Z"}'
GET crypto:btc:latest

# Increment counter
INCR message_count
```

### **List Operations (for queues)**

```bash
# Push to list (queue)
LPUSH price_updates "BTC:45000"
LPUSH price_updates "ETH:3200"

# Pop from list
RPOP price_updates

# Get list length
LLEN price_updates
```

### **Monitoring**

```bash
# Monitor all commands in real-time
MONITOR

# Get Redis info
INFO

# Check memory usage
INFO memory

# Number of keys
DBSIZE
```

---

## 🔌 Connection from Different Services

### **From Python Producer/Consumer**

```python
# PostgreSQL
import psycopg2
conn = psycopg2.connect(
    host="localhost",  # host machine
    port=5432,
    database="crypto_db",
    user="crypto_user",
    password="crypto_pass"
)

# Redis
import redis
r = redis.Redis(host='localhost', port=6379)
```

### **From Flink Job (Inside Docker)**

```java
// PostgreSQL JDBC
String jdbcUrl = "jdbc:postgresql://postgres:5432/crypto_db";
String username = "crypto_user";
String password = "crypto_pass";

// Note: Use container name "postgres", not "localhost"
```

### **From Another Container**

```yaml
# In docker-compose.yml, any service can connect to:
# - PostgreSQL at: postgres:5432
# - Redis at: redis:6379

# Example:
my-app:
  environment:
    DATABASE_URL: postgresql://crypto_user:crypto_pass@postgres:5433/crypto_db
    REDIS_URL: redis://redis:6379
```

---

## 🛡️ Security Notes

**For Development:**
- ⚠️ These are default credentials for local development only
- ⚠️ Never commit passwords to Git (use .env files)
- ⚠️ pgAdmin password is weak intentionally for dev

**For Production:**
- Use environment variables for credentials
- Enable PostgreSQL SSL/TLS
- Set Redis password with `requirepass`
- Use connection pooling
- Restrict network access with firewall rules

---

## 🔄 Data Persistence

### **Where Data is Stored**

Docker volumes store data persistently:
```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect real-time-cryptocurrency-market-analyzer_postgres_data
```

### **Backup Data**

```bash
# Backup PostgreSQL
docker exec postgres pg_dump -U crypto_user crypto_db > backup.sql

# Restore PostgreSQL
docker exec -i postgres psql -U crypto_user crypto_db < backup.sql

# Backup Redis
docker exec redis redis-cli SAVE
docker cp redis:/data/dump.rdb ./redis-backup.rdb
```

### **Reset Everything**

```bash
# WARNING: This deletes all data!
docker-compose down -v
docker-compose up -d
```

---

## 📚 Additional Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Commands Reference](https://redis.io/commands)
- [psycopg2 Tutorial](https://www.psycopg.org/docs/)
- [redis-py Documentation](https://redis-py.readthedocs.io/)

---

**Keep this file handy for quick database access throughout the project!** 💾
