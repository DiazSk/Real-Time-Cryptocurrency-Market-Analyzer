"""
Simple Cryptocurrency Price Consumer
Reads messages from Kafka and prints to console (basic filtering)

Author: Zaid
Phase 2, Week 4, Day 4-7
"""

import json
import logging
import sys
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError

# Import from src package
from src.config import KAFKA_CONSUMER_CONFIG, KAFKA_TOPIC_CRYPTO_PRICES, LOG_LEVEL

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleCryptoConsumer:
    """
    Simple consumer that reads cryptocurrency prices from Kafka
    and prints them to console with basic filtering
    """

    def __init__(self, filter_symbol: str = None):
        """
        Initialize consumer

        Args:
            filter_symbol: Optional symbol to filter (e.g., 'BTC'), None for all
        """
        self.consumer = None
        self.filter_symbol = filter_symbol
        self.message_count = 0
        self.filtered_count = 0

        logger.info(f"Initializing SimpleCryptoConsumer")
        if filter_symbol:
            logger.info(f"Filtering for symbol: {filter_symbol}")
        else:
            logger.info("No filter - consuming all cryptocurrencies")

    def connect_kafka(self):
        """Establish connection to Kafka and subscribe to topic"""
        try:
            self.consumer = KafkaConsumer(
                KAFKA_TOPIC_CRYPTO_PRICES, **KAFKA_CONSUMER_CONFIG
            )
            logger.info(f"Connected to Kafka topic: {KAFKA_TOPIC_CRYPTO_PRICES}")
            logger.info(f"Consumer group: {KAFKA_CONSUMER_CONFIG['group_id']}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            return False

    def process_message(self, message):
        """
        Process a single message from Kafka

        Args:
            message: Kafka message object
        """
        try:
            # Parse JSON message
            data = json.loads(message.value)

            symbol = data.get("symbol")
            price = data.get("price_usd")
            volume_24h = data.get("volume_24h")
            change_24h = data.get("price_change_24h")
            timestamp = data.get("timestamp")

            # Apply filter if set
            if self.filter_symbol and symbol != self.filter_symbol:
                self.filtered_count += 1
                return

            # Print formatted price update
            self.message_count += 1

            print(f"\n{'=' * 70}")
            print(f"Message #{self.message_count}")
            print(f"{'=' * 70}")
            print(f"Symbol:          {symbol}")
            print(
                f"Price:           ${price:,.2f}" if price else "Price:           N/A"
            )
            print(
                f"24h Volume:      ${volume_24h:,.0f}"
                if volume_24h
                else "24h Volume:      N/A"
            )
            print(
                f"24h Change:      {change_24h:+.2f}%"
                if change_24h
                else "24h Change:      N/A"
            )
            print(f"Timestamp:       {timestamp}")
            print(f"Partition:       {message.partition}")
            print(f"Offset:          {message.offset}")
            print(f"{'=' * 70}\n")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    def run(self):
        """Main consumer loop"""
        logger.info("=" * 60)
        logger.info("Starting Cryptocurrency Price Consumer")
        logger.info("=" * 60)
        logger.info(f"Topic: {KAFKA_TOPIC_CRYPTO_PRICES}")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Connect to Kafka
        if not self.connect_kafka():
            logger.error("Cannot start consumer without Kafka connection")
            return

        try:
            # Consume messages
            for message in self.consumer:
                self.process_message(message)

        except KeyboardInterrupt:
            logger.info("\nReceived interrupt signal, shutting down...")

        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        if self.consumer:
            logger.info("Closing Kafka consumer...")
            try:
                self.consumer.close()
            except (ValueError, OSError) as e:
                # Known issue with kafka-python-ng on Windows Python 3.13
                logger.warning(
                    f"Ignoring cleanup error (Windows/Python 3.13 issue): {e}"
                )

        # Statistics
        logger.info("=" * 60)
        logger.info("Consumer Statistics")
        logger.info("=" * 60)
        logger.info(f"Messages processed: {self.message_count}")
        if self.filter_symbol:
            logger.info(f"Messages filtered out: {self.filtered_count}")
        logger.info("=" * 60)
        logger.info("Consumer shutdown complete")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Simple Cryptocurrency Price Consumer")
    parser.add_argument(
        "--filter",
        type=str,
        help="Filter for specific cryptocurrency symbol (e.g., BTC)",
        default=None,
    )

    args = parser.parse_args()

    consumer = SimpleCryptoConsumer(filter_symbol=args.filter)
    consumer.run()


if __name__ == "__main__":
    main()
