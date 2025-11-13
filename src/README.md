# Source Code - Real-Time Cryptocurrency Market Analyzer

This directory contains the Python application code for the cryptocurrency data pipeline.

---

## 📁 Structure

```
src/
├── config.py                      # Central configuration
├── producers/
│   ├── __init__.py
│   └── crypto_price_producer.py   # CoinGecko API → Kafka producer
├── consumers/
│   ├── __init__.py
│   └── simple_consumer.py          # Kafka → Console consumer
└── utils/                          # Helper functions (future)
    └── __init__.py
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install requirements
pip install -r ../requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp ../.env.example ../.env

# Edit if needed (defaults work for local Docker setup)
```

### 3. Run Producer

```bash
python producers/crypto_price_producer.py
```

### 4. Run Consumer (in separate terminal)

```bash
python consumers/simple_consumer.py

# Or with filter
python consumers/simple_consumer.py --filter BTC
```

---

## 📦 Components

### config.py

Central configuration file containing:
- Kafka connection settings
- Database connection strings
- API configuration (CoinGecko)
- Feature flags
- Helper functions

**Usage:**
```python
from config import KAFKA_TOPIC_CRYPTO_PRICES, get_crypto_symbols
```

---

### producers/crypto_price_producer.py

Fetches cryptocurrency prices from CoinGecko API and produces to Kafka.

**Features:**
- ✅ Rate limiting (respects CoinGecko free tier: 10-50 req/min)
- ✅ Retry logic (handles transient failures)
- ✅ Data validation (price ranges, required fields)
- ✅ Structured logging
- ✅ Keyed messages (symbol → partition affinity)
- ✅ Graceful shutdown

**Configuration:**
```python
# In config.py
PRODUCER_FETCH_INTERVAL = 10  # seconds between fetches
CRYPTO_IDS = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum'
}
```

**Run:**
```bash
python producers/crypto_price_producer.py
```

---

### consumers/simple_consumer.py

Reads cryptocurrency prices from Kafka and prints to console.

**Features:**
- ✅ Optional filtering by cryptocurrency symbol
- ✅ Formatted console output
- ✅ Partition and offset tracking
- ✅ Consumer group participation
- ✅ Statistics on shutdown

**Run:**
```bash
# All cryptocurrencies
python consumers/simple_consumer.py

# Filter for BTC only
python consumers/simple_consumer.py --filter BTC

# Filter for ETH only
python consumers/simple_consumer.py --filter ETH
```

---

## 🔧 Configuration

All configuration in `config.py` can be overridden via environment variables in `.env`.

**Key Settings:**

| Setting | Default | Description |
|---------|---------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | localhost:9092 | Kafka broker address |
| `KAFKA_TOPIC` | crypto-prices | Topic for price data |
| `PRODUCER_FETCH_INTERVAL` | 10 | Seconds between price fetches |
| `API_RATE_LIMIT_DELAY` | 6 | Seconds to wait after rate limit |

---

## 🧪 Testing

### Manual Testing

1. **Start infrastructure:**
   ```bash
   docker-compose up -d
   ```

2. **Create Kafka topic:**
   - Via Kafka UI: http://localhost:8081
   - Name: `crypto-prices`
   - Partitions: 3

3. **Run producer:**
   ```bash
   python producers/crypto_price_producer.py
   ```

4. **Verify in Kafka UI:**
   - Check messages appearing in topic
   - Verify partition assignment

5. **Run consumer:**
   ```bash
   python consumers/simple_consumer.py
   ```

6. **Verify console output:**
   - Formatted price updates
   - Real-time data flow

---

## 📊 Message Format

**Kafka Message:**
```json
{
  "symbol": "BTC",
  "coin_id": "bitcoin",
  "price_usd": 45234.56,
  "volume_24h": 28456789012.34,
  "market_cap": 886543210987.65,
  "price_change_24h": 2.34,
  "last_updated": 1699876543,
  "timestamp": "2025-11-12T10:30:45.123456",
  "producer_id": "python-producer-v1",
  "message_id": "BTC-1699876545123"
}
```

**Key:** `"BTC"` or `"ETH"`  
**Partition:** Hash(key) % 3  
**Serialization:** UTF-8 encoded JSON string

---

## 🎯 Future Enhancements

### Week 5-7 (Flink Integration):
- [ ] Flink streaming jobs (Java/Scala)
- [ ] Window aggregations (1-minute OHLC)
- [ ] Moving averages
- [ ] Trend detection
- [ ] Write to PostgreSQL and Redis

### Week 8-9 (API & Visualization):
- [ ] FastAPI REST endpoints
- [ ] WebSocket for live updates
- [ ] Streamlit dashboard
- [ ] Historical charts

---

## 📚 Resources

- [CoinGecko API Docs](https://www.coingecko.com/en/api/documentation)
- [kafka-python Documentation](https://kafka-python.readthedocs.io/)
- [Kafka Producer Configs](https://kafka.apache.org/documentation/#producerconfigs)
- [Kafka Consumer Configs](https://kafka.apache.org/documentation/#consumerconfigs)

---

**Ready to stream real cryptocurrency data!** 🚀
