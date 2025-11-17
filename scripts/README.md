# Scripts Directory

This folder contains deployment and infrastructure management utilities.

## Contents

### **Flink Deployment:**
- **deploy_postgres_sink.bat** - Deploys Flink job with PostgreSQL sink
- **deploy_redis_sink.bat** - Deploys Flink job with Redis cache sink  
- **redeploy_flink.bat** - Rebuilds and redeploys Flink job with latest changes

### **Infrastructure Management:**
- **restart_kafka.bat** - Restarts Kafka broker (fixes common issues)

## Usage

### Deploy Flink Job:
```bash
# After making changes to Flink Java code
scripts\redeploy_flink.bat
```

### Fix Kafka Issues:
```bash
# If Kafka broker is unresponsive
scripts\restart_kafka.bat
```

### Deploy Specific Sinks:
```bash
# Deploy with PostgreSQL sink only
scripts\deploy_postgres_sink.bat

# Deploy with Redis sink only
scripts\deploy_redis_sink.bat
```

## Development Workflow

```
1. Modify Flink Java code
2. Run: scripts\redeploy_flink.bat
3. Verify in Flink Web UI: http://localhost:8082
4. Check logs: docker logs flink-taskmanager
```

**Note:** These scripts are for development/debugging. Production deployment would use CI/CD pipelines.
