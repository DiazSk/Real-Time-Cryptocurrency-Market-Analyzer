"""
Configuration file for Real-Time Cryptocurrency Market Analyzer
Author: Zaid
Phase 2, Week 4
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================
# Kafka Configuration
# ============================================
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_CRYPTO_PRICES = os.getenv("KAFKA_TOPIC", "crypto-prices")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "crypto-analyzer-group")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")

# Producer Configuration
KAFKA_PRODUCER_CONFIG = {
    "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
    "value_serializer": lambda v: v.encode("utf-8"),  # JSON string serialization
    "key_serializer": lambda k: k.encode("utf-8") if k else None,
    "acks": "all",  # Wait for all replicas to acknowledge (strongest durability)
    "retries": 3,  # Retry failed sends
    "max_in_flight_requests_per_connection": 1,  # Ensure ordering
    "compression_type": "gzip",  # Compress messages
}

# Consumer Configuration
KAFKA_CONSUMER_CONFIG = {
    "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
    "group_id": KAFKA_CONSUMER_GROUP,
    "auto_offset_reset": "earliest",  # Start from beginning if no offset
    "enable_auto_commit": False,  # Manual commit for exactly-once
    "value_deserializer": lambda v: v.decode("utf-8"),
    "key_deserializer": lambda k: k.decode("utf-8") if k else None,
}

# ============================================
# CoinGecko API Configuration
# ============================================
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
COINGECKO_API_KEY = os.getenv(
    "COINGECKO_API_KEY", None
)  # Optional, for higher rate limits

# Cryptocurrency IDs (CoinGecko format)
CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    # Add more as needed:
    # 'SOL': 'solana',
    # 'ADA': 'cardano',
    # 'DOT': 'polkadot',
}

# API Request Configuration
API_REQUEST_TIMEOUT = 10  # seconds
API_RATE_LIMIT_DELAY = 6  # seconds between requests (10 requests/minute for free tier)
API_MAX_RETRIES = 3

# ============================================
# PostgreSQL Configuration
# ============================================
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5433")
POSTGRES_DB = os.getenv("POSTGRES_DB", "crypto_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "crypto_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "crypto_pass")

# Connection String
POSTGRES_CONNECTION_STRING = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# ============================================
# Redis Configuration
# ============================================
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Redis Key Patterns
REDIS_KEY_LATEST_PRICE = "crypto:{symbol}:latest"
REDIS_KEY_PRICE_HISTORY = "crypto:{symbol}:history"
REDIS_KEY_STATS_24H = "crypto:{symbol}:stats:24h"

# ============================================
# Application Configuration
# ============================================
# Producer Settings
PRODUCER_FETCH_INTERVAL = 5  # seconds between price fetches
PRODUCER_RUN_DURATION = 300  # seconds (5 minutes for testing), 0 for infinite

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "json"  # 'json' or 'console'

# ============================================
# Data Validation
# ============================================
# Price change thresholds for anomaly detection
MAX_PRICE_CHANGE_PERCENT = 50  # Alert if price changes > 50% in one update
MIN_PRICE_VALUE = 0.0001  # Minimum valid price (prevent zero/negative)
MAX_PRICE_VALUE = 1000000  # Maximum valid price (sanity check)

# ============================================
# Development vs Production
# ============================================
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG_MODE = ENVIRONMENT == "development"

# ============================================
# Feature Flags
# ============================================
ENABLE_PRICE_VALIDATION = True  # Validate price data before producing
ENABLE_DUPLICATE_DETECTION = True  # Check for duplicate messages
ENABLE_REDIS_CACHING = True  # Cache latest prices to Redis
ENABLE_METRICS_LOGGING = True  # Log performance metrics


# ============================================
# Helper Functions
# ============================================
def get_kafka_topic():
    """Get the Kafka topic name for cryptocurrency prices"""
    return KAFKA_TOPIC_CRYPTO_PRICES


def get_crypto_symbols():
    """Get list of cryptocurrency symbols to track"""
    return list(CRYPTO_IDS.keys())


def get_coingecko_id(symbol):
    """Get CoinGecko API ID for a cryptocurrency symbol"""
    return CRYPTO_IDS.get(symbol.upper())


def validate_price(price):
    """Validate if a price value is within acceptable range"""
    return MIN_PRICE_VALUE <= price <= MAX_PRICE_VALUE


def format_redis_key(pattern, symbol):
    """Format Redis key with cryptocurrency symbol"""
    return pattern.format(symbol=symbol.upper())


# ============================================
# Configuration Validation
# ============================================
def validate_config():
    """Validate configuration on startup"""
    issues = []

    if not KAFKA_BOOTSTRAP_SERVERS:
        issues.append("KAFKA_BOOTSTRAP_SERVERS not configured")

    if not POSTGRES_HOST:
        issues.append("POSTGRES_HOST not configured")

    if not REDIS_HOST:
        issues.append("REDIS_HOST not configured")

    if not CRYPTO_IDS:
        issues.append("No cryptocurrencies configured in CRYPTO_IDS")

    if issues:
        raise ValueError(f"Configuration validation failed: {', '.join(issues)}")

    return True


# Validate on import
if __name__ != "__main__":
    validate_config()
