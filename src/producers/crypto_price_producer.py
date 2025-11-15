"""
Cryptocurrency Price Producer
Fetches real-time cryptocurrency prices from CoinGecko API and produces to Kafka

Author: Zaid
Phase 2, Week 4, Day 1-3
"""

import json
import time
import logging
import sys
from datetime import datetime
from typing import Dict, Optional, List
import requests
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Add parent directory to path for imports
sys.path.append('..')
from config import (
    KAFKA_PRODUCER_CONFIG,
    KAFKA_TOPIC_CRYPTO_PRICES,
    COINGECKO_BASE_URL,
    CRYPTO_IDS,
    API_REQUEST_TIMEOUT,
    API_RATE_LIMIT_DELAY,
    API_MAX_RETRIES,
    PRODUCER_FETCH_INTERVAL,
    PRODUCER_RUN_DURATION,
    LOG_LEVEL,
    ENABLE_PRICE_VALIDATION,
    validate_price,
    get_crypto_symbols
)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CryptoPriceProducer:
    """
    Producer that fetches cryptocurrency prices from CoinGecko API
    and publishes them to Kafka topic
    """
    
    def __init__(self):
        """Initialize the producer"""
        self.producer = None
        self.crypto_symbols = get_crypto_symbols()
        self.start_time = None
        self.message_count = 0
        self.error_count = 0
        
        logger.info(f"Initializing CryptoPriceProducer for {len(self.crypto_symbols)} cryptocurrencies")
        logger.info(f"Symbols: {', '.join(self.crypto_symbols)}")
    
    def connect_kafka(self):
        """Establish connection to Kafka broker"""
        try:
            self.producer = KafkaProducer(**KAFKA_PRODUCER_CONFIG)
            logger.info(f"Connected to Kafka at {KAFKA_PRODUCER_CONFIG['bootstrap_servers']}")
            logger.info(f"Will produce to topic: {KAFKA_TOPIC_CRYPTO_PRICES}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            return False
    
    def fetch_crypto_prices(self, symbols: List[str]) -> Optional[Dict]:
        """
        Fetch current prices for given cryptocurrency symbols from CoinGecko API
        
        Args:
            symbols: List of crypto symbols (e.g., ['BTC', 'ETH'])
            
        Returns:
            Dictionary with price data or None if error
        """
        # Convert symbols to CoinGecko IDs
        coin_ids = [CRYPTO_IDS[symbol] for symbol in symbols]
        ids_param = ','.join(coin_ids)
        
        # API endpoint for simple price
        url = f"{COINGECKO_BASE_URL}/simple/price"
        
        params = {
            'ids': ids_param,
            'vs_currencies': 'usd',
            'include_24hr_vol': 'true',
            'include_24hr_change': 'true',
            'include_market_cap': 'true',
            'include_last_updated_at': 'true'
        }
        
        # Retry logic
        for attempt in range(API_MAX_RETRIES):
            try:
                logger.debug(f"Fetching prices (attempt {attempt + 1}/{API_MAX_RETRIES})")
                response = requests.get(url, params=params, timeout=API_REQUEST_TIMEOUT)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Successfully fetched prices for {len(data)} cryptocurrencies")
                    return data
                
                elif response.status_code == 429:
                    # Rate limit exceeded
                    logger.warning("Rate limit exceeded, waiting before retry...")
                    time.sleep(API_RATE_LIMIT_DELAY * 2)
                    
                else:
                    logger.error(f"API returned status code {response.status_code}: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1})")
                time.sleep(2)
                
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error: {e}")
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Unexpected error fetching prices: {e}")
                
        logger.error(f"Failed to fetch prices after {API_MAX_RETRIES} attempts")
        self.error_count += 1
        return None
    
    def create_price_message(self, symbol: str, data: Dict) -> Dict:
        """
        Create a structured message for Kafka from API response
        
        Args:
            symbol: Crypto symbol (e.g., 'BTC')
            data: Price data from CoinGecko API
            
        Returns:
            Formatted message dictionary
        """
        coin_id = CRYPTO_IDS[symbol]
        coin_data = data.get(coin_id, {})
        
        message = {
            'symbol': symbol,
            'coin_id': coin_id,
            'price_usd': coin_data.get('usd'),
            'volume_24h': coin_data.get('usd_24h_vol'),
            'market_cap': coin_data.get('usd_market_cap'),
            'price_change_24h': coin_data.get('usd_24h_change'),
            'last_updated': coin_data.get('last_updated_at'),
            'timestamp': datetime.utcnow().isoformat() + 'Z',  # Add Z for UTC timezone
            'producer_id': 'python-producer-v1',
            'message_id': f"{symbol}-{int(time.time() * 1000)}"
        }
        
        return message
    
    def validate_message(self, message: Dict) -> bool:
        """
        Validate message data before sending to Kafka
        
        Args:
            message: Message dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not ENABLE_PRICE_VALIDATION:
            return True
        
        # Check required fields
        required_fields = ['symbol', 'price_usd', 'timestamp']
        for field in required_fields:
            if field not in message or message[field] is None:
                logger.warning(f"Message missing required field: {field}")
                return False
        
        # Validate price range
        price = message['price_usd']
        if not validate_price(price):
            logger.warning(f"Invalid price for {message['symbol']}: {price}")
            return False
        
        return True
    
    def produce_message(self, message: Dict):
        """
        Send message to Kafka topic
        
        Args:
            message: Message dictionary to send
        """
        try:
            # Use symbol as key for partition assignment
            key = message['symbol']
            value = json.dumps(message)
            
            # Send to Kafka
            future = self.producer.send(
                KAFKA_TOPIC_CRYPTO_PRICES,
                key=key,
                value=value
            )
            
            # Wait for confirmation (optional, for debugging)
            record_metadata = future.get(timeout=10)
            
            self.message_count += 1
            
            logger.info(
                f"Produced: {message['symbol']} ${message['price_usd']:,.2f} "
                f"to partition {record_metadata.partition} "
                f"at offset {record_metadata.offset}"
            )
            
        except KafkaError as e:
            logger.error(f"Kafka error producing message: {e}")
            self.error_count += 1
            
        except Exception as e:
            logger.error(f"Unexpected error producing message: {e}")
            self.error_count += 1
    
    def run(self):
        """
        Main producer loop
        Fetches prices and produces to Kafka at regular intervals
        """
        logger.info("=" * 60)
        logger.info("Starting Cryptocurrency Price Producer")
        logger.info("=" * 60)
        logger.info(f"Fetch interval: {PRODUCER_FETCH_INTERVAL} seconds")
        logger.info(f"Target cryptocurrencies: {', '.join(self.crypto_symbols)}")
        logger.info(f"Kafka topic: {KAFKA_TOPIC_CRYPTO_PRICES}")
        
        if PRODUCER_RUN_DURATION > 0:
            logger.info(f"Will run for {PRODUCER_RUN_DURATION} seconds")
        else:
            logger.info("Will run indefinitely (Ctrl+C to stop)")
        
        # Connect to Kafka
        if not self.connect_kafka():
            logger.error("Cannot start producer without Kafka connection")
            return
        
        self.start_time = time.time()
        iteration = 0
        
        try:
            while True:
                iteration += 1
                iteration_start = time.time()
                
                logger.info(f"\n--- Iteration {iteration} ---")
                
                # Fetch prices from CoinGecko API
                price_data = self.fetch_crypto_prices(self.crypto_symbols)
                
                if price_data:
                    # Process each cryptocurrency
                    for symbol in self.crypto_symbols:
                        # Create message
                        message = self.create_price_message(symbol, price_data)
                        
                        # Validate message
                        if self.validate_message(message):
                            # Produce to Kafka
                            self.produce_message(message)
                        else:
                            logger.warning(f"Skipping invalid message for {symbol}")
                            self.error_count += 1
                else:
                    logger.error("Failed to fetch price data, skipping this iteration")
                
                # Calculate time for this iteration
                iteration_duration = time.time() - iteration_start
                logger.info(f"Iteration {iteration} completed in {iteration_duration:.2f}s")
                logger.info(f"Total messages produced: {self.message_count}, Errors: {self.error_count}")
                
                # Check if we should stop (based on duration)
                if PRODUCER_RUN_DURATION > 0:
                    elapsed = time.time() - self.start_time
                    if elapsed >= PRODUCER_RUN_DURATION:
                        logger.info(f"Reached run duration limit ({PRODUCER_RUN_DURATION}s), stopping...")
                        break
                
                # Wait for next iteration
                sleep_time = max(0, PRODUCER_FETCH_INTERVAL - iteration_duration)
                if sleep_time > 0:
                    logger.info(f"Waiting {sleep_time:.2f}s until next fetch...")
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("\nReceived interrupt signal, shutting down gracefully...")
            
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        if self.producer:
            logger.info("Flushing remaining messages...")
            self.producer.flush()
            logger.info("Closing Kafka producer...")
            self.producer.close()
        
        # Final statistics
        if self.start_time:
            total_runtime = time.time() - self.start_time
            logger.info("=" * 60)
            logger.info("Producer Statistics")
            logger.info("=" * 60)
            logger.info(f"Total runtime: {total_runtime:.2f} seconds")
            logger.info(f"Messages produced: {self.message_count}")
            logger.info(f"Errors encountered: {self.error_count}")
            if self.message_count > 0:
                logger.info(f"Average throughput: {self.message_count / total_runtime:.2f} messages/second")
                success_rate = (self.message_count / (self.message_count + self.error_count)) * 100
                logger.info(f"Success rate: {success_rate:.2f}%")
            logger.info("=" * 60)
        
        logger.info("Producer shutdown complete")


def main():
    """Main entry point"""
    producer = CryptoPriceProducer()
    producer.run()


if __name__ == "__main__":
    main()
