# Docker Compose Quick Reference

## 🚀 Essential Commands

### Starting Services
```bash
# Start all services in background
docker-compose up -d

# Start and view logs in real-time
docker-compose up

# Start specific service
docker-compose up -d kafka
```

### Stopping Services
```bash
# Stop all services (keeps data)
docker-compose stop

# Stop and remove containers (keeps volumes)
docker-compose down

# Nuclear option: remove everything including volumes
docker-compose down -v
```

### Viewing Status & Logs
```bash
# Check which containers are running
docker-compose ps

# View logs for all services
docker-compose logs

# View logs for specific service
docker-compose logs kafka

# Follow logs in real-time
docker-compose logs -f kafka

# View last 50 lines
docker-compose logs --tail=50 kafka
```

### Restarting Services
```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart kafka

# Rebuild and restart (after changing docker-compose.yml)
docker-compose up -d --build
```

### Debugging
```bash
# Execute command in running container
docker-compose exec kafka bash

# View resource usage
docker stats

# Inspect specific container
docker inspect kafka
```

---

## 🔍 Useful Combinations

**Fresh start after changing docker-compose.yml:**
```bash
docker-compose down
docker-compose up -d
```

**Check if Kafka is ready:**
```bash
docker-compose logs kafka | grep "started"
```

**See all running Docker containers:**
```bash
docker ps
```

**Clean up stopped containers:**
```bash
docker system prune
```

---

## 📊 Understanding Output

**`docker-compose ps` columns:**
- **Name**: Container name
- **Command**: What's running inside
- **State**: Up/Exit/Restarting
- **Ports**: Port mappings (host:container)

**Container States:**
- **Up**: Running successfully ✅
- **Up (health: starting)**: Starting up ⏳
- **Restarting**: Crashing and restarting ⚠️
- **Exit 0**: Stopped normally
- **Exit 1**: Stopped due to error ❌

---

## 🆘 Emergency Commands

**Kafka not responding:**
```bash
docker-compose restart kafka
```

**Everything broken:**
```bash
docker-compose down -v  # WARNING: Deletes all data
docker-compose up -d
```

**Check Docker resources:**
```bash
# In Docker Desktop:
# Settings → Resources → Advanced
# Increase Memory/CPU if needed
```

---

## 💡 Pro Tips

1. **Always check logs first**: `docker-compose logs <service>`
2. **Wait for Zookeeper**: Kafka needs 30s after Zookeeper starts
3. **Port conflicts**: Kill other services using same ports
4. **Clean state**: Use `down -v` only when you want fresh data

---

## 🔗 Access URLs (Default)

| Service | URL | Purpose |
|---------|-----|---------|
| Kafka UI | http://localhost:8080 | Visual Kafka management |
| Kafka | localhost:9092 | Producer/Consumer connections |
| Zookeeper | localhost:2181 | Metadata management |

---

**Save this file for quick reference during Phase 2!**
