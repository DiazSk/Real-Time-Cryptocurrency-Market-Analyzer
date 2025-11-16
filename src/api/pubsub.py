"""
Redis Pub/Sub Subscriber for Real-Time Updates
Phase 4 - Week 8 - Day 4-5

Listens to Redis Pub/Sub channel and broadcasts updates to WebSocket clients.
"""

import redis
import json
import logging
import asyncio
from typing import Callable, Optional
import threading

logger = logging.getLogger(__name__)


class RedisPubSubManager:
    """
    Manages Redis Pub/Sub subscriptions for real-time price updates
    """
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.pubsub = None
        self.redis_client = None
        self.subscriber_thread = None
        self.is_running = False
        self.message_handlers = []
        
    def connect(self):
        """
        Connect to Redis and subscribe to crypto updates channel
        """
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=None  # No timeout for Pub/Sub - wait indefinitely
            )
            
            # Test connection
            self.redis_client.ping()
            
            # Create Pub/Sub object
            self.pubsub = self.redis_client.pubsub()
            
            # Subscribe to crypto updates channel
            self.pubsub.subscribe("crypto:updates")
            
            logger.info(f"✅ Connected to Redis Pub/Sub: {self.redis_host}:{self.redis_port}")
            logger.info("📡 Subscribed to channel: crypto:updates")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis Pub/Sub: {e}")
            raise
    
    def add_handler(self, handler: Callable):
        """
        Add a message handler callback
        
        Args:
            handler: Async function to call with each message
        """
        self.message_handlers.append(handler)
        logger.info(f"Added message handler. Total handlers: {len(self.message_handlers)}")
    
    def remove_handler(self, handler: Callable):
        """
        Remove a message handler
        """
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)
            logger.info(f"Removed message handler. Total handlers: {len(self.message_handlers)}")
    
    async def _handle_message(self, message_data: str):
        """
        Process and broadcast message to all handlers
        """
        try:
            # Parse JSON message
            data = json.loads(message_data)
            
            # Call all registered handlers
            for handler in self.message_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def start_listening(self):
        """
        Start listening to Redis Pub/Sub messages in a background thread
        """
        if self.is_running:
            logger.warning("Subscriber already running")
            return
        
        def listen_loop():
            """
            Background thread function to listen for messages
            """
            logger.info("🎧 Starting Redis Pub/Sub listener thread...")
            self.is_running = True
            
            try:
                # Get message immediately after subscription (will be subscribe confirmation)
                # This ensures the pubsub object is properly initialized
                while self.is_running:
                    message = self.pubsub.get_message(timeout=30.0)  # 30-second timeout
                    
                    if message is None:
                        continue  # No message, keep waiting
                    
                    # Process only actual messages (not subscribe confirmations)
                    if message['type'] == 'message':
                        message_data = message['data']
                        logger.debug(f"📨 Received Pub/Sub message: {message_data[:100]}...")
                        
                        # Schedule async handler
                        try:
                            # Create event loop for this thread if needed
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self._handle_message(message_data))
                            loop.close()
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
            
            except Exception as e:
                logger.error(f"Error in listen loop: {e}")
            finally:
                self.is_running = False
                logger.info("🛑 Redis Pub/Sub listener thread stopped")
        
        # Start listener in background thread
        self.subscriber_thread = threading.Thread(target=listen_loop, daemon=True)
        self.subscriber_thread.start()
        
        logger.info("✅ Redis Pub/Sub listener started")
    
    def stop_listening(self):
        """
        Stop listening to Redis Pub/Sub
        """
        if not self.is_running:
            return
        
        logger.info("Stopping Redis Pub/Sub listener...")
        self.is_running = False
        
        if self.pubsub:
            try:
                self.pubsub.unsubscribe()
                self.pubsub.close()
            except Exception as e:
                logger.error(f"Error closing pubsub: {e}")
        
        if self.redis_client:
            try:
                self.redis_client.close()
            except Exception as e:
                logger.error(f"Error closing redis client: {e}")
        
        logger.info("✅ Redis Pub/Sub listener stopped")


# Global pub/sub manager instance
pubsub_manager = RedisPubSubManager()
