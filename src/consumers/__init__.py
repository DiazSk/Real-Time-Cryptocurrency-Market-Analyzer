"""
Consumers package for Real-Time Cryptocurrency Market Analyzer
Contains Kafka consumers for processing cryptocurrency data streams
"""

from .simple_consumer import SimpleCryptoConsumer

__all__ = ['SimpleCryptoConsumer']
