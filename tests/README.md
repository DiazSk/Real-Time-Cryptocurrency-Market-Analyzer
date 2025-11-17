# Tests Directory

This folder contains testing utilities and scripts for validating the cryptocurrency market analyzer.

## Contents

### **Integration Tests:**
- **test_spike.py** - Triggers synthetic price spike for anomaly detection testing
- **test_pubsub.ps1** - Validates Redis Pub/Sub event-driven architecture
- **test_api_enhancements.ps1** - Tests API pagination, stats, and performance headers

### **Consumer Utilities:**
- **start_alert_consumer.bat** - Launches Kafka consumer for crypto-alerts topic
- **start_simple_consumer.bat** - Launches basic Kafka consumer for debugging

## Usage

### Test Anomaly Detection:
```bash
python tests/test_spike.py
# Wait 1-2 minutes
# Check dashboard for alert notification
```

### Test Redis Pub/Sub:
```powershell
.\tests\test_pubsub.ps1
# Verifies event-driven WebSocket architecture
```

### Test API Enhancements:
```powershell
.\tests\test_api_enhancements.ps1
# Tests pagination, ordering, stats endpoints
```

## Running All Tests

```bash
# From project root
python tests/test_spike.py
powershell -File tests/test_pubsub.ps1
powershell -File tests/test_api_enhancements.ps1
```

**Note:** These are integration tests, not unit tests. Require full infrastructure running (docker-compose up -d).
