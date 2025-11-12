# Phase 2 - Week 3 - Day 3-4 (Coming Soon)

## 🎯 Goal: Add PostgreSQL and Redis to the stack

This will be unlocked after you complete Day 1-2!

### What we'll add:

**PostgreSQL:**
- Store historical cryptocurrency data
- Time-series tables for price history
- Aggregated metrics storage

**Redis:**
- Cache latest prices for fast API responses
- Store real-time aggregations
- Leaderboards / trending coins

---

### Preview of docker-compose additions:

```yaml
postgres:
  image: postgres:15-alpine
  container_name: postgres
  environment:
    POSTGRES_DB: crypto_db
    POSTGRES_USER: crypto_user
    POSTGRES_PASSWORD: crypto_pass
  ports:
    - "5432:5432"

redis:
  image: redis:7-alpine
  container_name: redis
  ports:
    - "6379:6379"
```

---

**Complete Day 1-2 first, then come back here!** 💪
