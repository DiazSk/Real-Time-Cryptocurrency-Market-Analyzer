"""
Cryptocurrency Price Producer.
Fetches real-time prices from the CoinGecko API and publishes them to Kafka.
"""

import json
import time
import logging
import sys
from datetime import datetime, timezone
from typing import Dict, Optional, List

import requests
from kafka import KafkaProducer
from kafka.errors import KafkaError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
    RetryError,
)

from src.config import (
    KAFKA_PRODUCER_CONFIG,
    KAFKA_TOPIC_CRYPTO_PRICES,
    COINGECKO_BASE_URL,
    CRYPTO_IDS,
    API_REQUEST_TIMEOUT,
    API_MAX_RETRIES,
    PRODUCER_FETCH_INTERVAL,
    PRODUCER_RUN_DURATION,
    LOG_LEVEL,
    ENABLE_PRICE_VALIDATION,
    validate_price,
    get_crypto_symbols,
)

logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CryptoPriceProducer:
    """Fetches cryptocurrency prices from CoinGecko and publishes them to a Kafka topic."""

    def __init__(self):
        self.producer = None
        self.crypto_symbols = get_crypto_symbols()
        self.start_time = None
        self.message_count = 0
        self.error_count = 0
        logger.info(
            "Initializing CryptoPriceProducer for %d cryptocurrencies: %s",
            len(self.crypto_symbols),
            ", ".join(self.crypto_symbols),
        )

    def connect_kafka(self) -> bool:
        try:
            self.producer = KafkaProducer(**KAFKA_PRODUCER_CONFIG)
            logger.info(
                "Connected to Kafka at %s, producing to topic: %s",
                KAFKA_PRODUCER_CONFIG["bootstrap_servers"],
                KAFKA_TOPIC_CRYPTO_PRICES,
            )
            return True
        except Exception as e:
            logger.error("Failed to connect to Kafka: %s", e)
            return False

    @retry(
        # Retry on transport failures and rate limits.  HTTP 429 is mapped to IOError
        # before raise_for_status() so it enters the same backoff path as connection errors.
        retry=retry_if_exception_type(
            (requests.exceptions.Timeout, requests.exceptions.ConnectionError, IOError)
        ),
        wait=wait_random_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(API_MAX_RETRIES),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call_coingecko(self, url: str, params: dict) -> dict:
        """
        Single HTTP call to CoinGecko, decorated with tenacity retry logic.
        Raises IOError on HTTP 429 so the exponential-backoff path handles rate limits.
        Non-retryable HTTP errors (4xx except 429) propagate immediately via raise_for_status().
        """
        response = requests.get(url, params=params, timeout=API_REQUEST_TIMEOUT)
        if response.status_code == 429:
            raise IOError("CoinGecko rate limit exceeded (HTTP 429)")
        response.raise_for_status()
        return response.json()

    def fetch_crypto_prices(self, symbols: List[str]) -> Optional[Dict]:
        """Fetch current prices for the given symbols, returning None on permanent failure."""
        coin_ids = [CRYPTO_IDS[symbol] for symbol in symbols]
        url = f"{COINGECKO_BASE_URL}/simple/price"
        params = {
            "ids": ",".join(coin_ids),
            "vs_currencies": "usd",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
            "include_market_cap": "true",
            "include_last_updated_at": "true",
        }

        try:
            data = self._call_coingecko(url, params)
            logger.debug("Fetched prices for %d coins", len(data))
            return data
        except RetryError:
            logger.error("CoinGecko fetch failed after %d attempts", API_MAX_RETRIES)
        except requests.exceptions.HTTPError as e:
            logger.error("Non-retryable HTTP error from CoinGecko: %s", e)
        except Exception as e:
            logger.error("Unexpected error fetching prices: %s", e)

        self.error_count += 1
        return None

    def create_price_message(self, symbol: str, data: Dict) -> Dict:
        coin_id = CRYPTO_IDS[symbol]
        coin_data = data.get(coin_id, {})
        return {
            "symbol": symbol,
            "coin_id": coin_id,
            "price_usd": coin_data.get("usd"),
            "volume_24h": coin_data.get("usd_24h_vol"),
            "market_cap": coin_data.get("usd_market_cap"),
            "price_change_24h": coin_data.get("usd_24h_change"),
            "last_updated": coin_data.get("last_updated_at"),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "producer_id": "python-producer-v1",
            "message_id": f"{symbol}-{int(time.time() * 1000)}",
        }

    def validate_message(self, message: Dict) -> bool:
        if not ENABLE_PRICE_VALIDATION:
            return True
        for field in ("symbol", "price_usd", "timestamp"):
            if field not in message or message[field] is None:
                logger.warning("Message missing required field: %s", field)
                return False
        if not validate_price(message["price_usd"]):
            logger.warning("Invalid price for %s: %s", message["symbol"], message["price_usd"])
            return False
        return True

    def produce_message(self, message: Dict):
        try:
            future = self.producer.send(
                KAFKA_TOPIC_CRYPTO_PRICES,
                key=message["symbol"],
                value=json.dumps(message),
            )
            meta = future.get(timeout=10)
            self.message_count += 1
            logger.info(
                "Produced: %s $%s → partition %d offset %d",
                message["symbol"], f"{message['price_usd']:,.2f}", meta.partition, meta.offset,
            )
        except KafkaError as e:
            logger.error("Kafka error producing message: %s", e)
            self.error_count += 1
        except Exception as e:
            logger.error("Unexpected error producing message: %s", e)
            self.error_count += 1

    def run(self):
        logger.info("Starting Cryptocurrency Price Producer")
        logger.info("Fetch interval: %ss | Topic: %s | Symbols: %s",
                    PRODUCER_FETCH_INTERVAL, KAFKA_TOPIC_CRYPTO_PRICES,
                    ", ".join(self.crypto_symbols))

        if not self.connect_kafka():
            logger.error("Cannot start producer without Kafka connection")
            return

        self.start_time = time.time()
        iteration = 0

        try:
            while True:
                iteration += 1
                iteration_start = time.time()
                logger.info("--- Iteration %d ---", iteration)

                price_data = self.fetch_crypto_prices(self.crypto_symbols)
                if price_data:
                    for symbol in self.crypto_symbols:
                        message = self.create_price_message(symbol, price_data)
                        if self.validate_message(message):
                            self.produce_message(message)
                        else:
                            logger.warning("Skipping invalid message for %s", symbol)
                            self.error_count += 1
                else:
                    logger.error("Failed to fetch price data, skipping iteration %d", iteration)

                iteration_duration = time.time() - iteration_start
                logger.info(
                    "Iteration %d completed in %.2fs | produced: %d errors: %d",
                    iteration, iteration_duration, self.message_count, self.error_count,
                )

                if PRODUCER_RUN_DURATION > 0:
                    if time.time() - self.start_time >= PRODUCER_RUN_DURATION:
                        logger.info("Reached run duration limit (%ss), stopping.", PRODUCER_RUN_DURATION)
                        break

                sleep_time = max(0, PRODUCER_FETCH_INTERVAL - iteration_duration)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down gracefully...")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.producer:
            logger.info("Flushing and closing Kafka producer...")
            self.producer.flush()
            self.producer.close()

        if self.start_time:
            total_runtime = time.time() - self.start_time
            logger.info(
                "Shutdown | runtime: %.2fs | produced: %d | errors: %d",
                total_runtime, self.message_count, self.error_count,
            )


def main():
    CryptoPriceProducer().run()


if __name__ == "__main__":
    main()
