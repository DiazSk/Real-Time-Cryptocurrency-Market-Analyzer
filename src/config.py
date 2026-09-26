"""
Producer configuration. The API has its own pydantic settings in src/api/config.py.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ============================================
# Kafka
# ============================================
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
# A new variable name on purpose: older .env files set KAFKA_TOPIC=crypto-prices.
KAFKA_TOPIC_TRADES = os.getenv("KAFKA_TRADES_TOPIC", "crypto-trades")

KAFKA_PRODUCER_CONFIG = {
    "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
    "key_serializer": lambda k: k.encode("utf-8"),
    "value_serializer": lambda v: v.encode("utf-8"),
    "acks": "all",
    "retries": 5,
    # One in-flight request keeps per-partition order even when a send is retried.
    # A retry duplicate therefore lands right after the original, which is what
    # lets Flink's DedupByTradeId drop it with a single last-seen trade_id per symbol.
    "max_in_flight_requests_per_connection": 1,
    "linger_ms": 20,
    "compression_type": "gzip",
}

# ============================================
# Coinbase Exchange public market data
# ============================================
COINBASE_WS_URL = os.getenv("COINBASE_WS_URL", "wss://ws-feed.exchange.coinbase.com")

# ============================================
# PostgreSQL (symbol registry)
# ============================================
POSTGRES_CONNECT_KWARGS = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5433")),
    "database": os.getenv("POSTGRES_DB", "crypto_db"),
    "user": os.getenv("POSTGRES_USER", "crypto_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "crypto_pass"),
}

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ============================================
# Redis (crypto:trades tick stream for the live line chart)
# ============================================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
