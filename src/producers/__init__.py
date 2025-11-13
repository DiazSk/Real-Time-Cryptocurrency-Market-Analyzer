"""
Producers package for Real-Time Cryptocurrency Market Analyzer
Contains Kafka producers for streaming cryptocurrency data
"""

from .crypto_price_producer import CryptoPriceProducer

__all__ = ['CryptoPriceProducer']
