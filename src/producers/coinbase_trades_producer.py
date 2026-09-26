"""
Coinbase trade producer.

Streams every trade for the tracked products from Coinbase Exchange's public
`matches` WebSocket channel and publishes one Kafka message per trade to
`crypto-trades`, keyed by symbol.

Completeness: Coinbase trade_ids are contiguous per product, so a jump in
trade_id is a count of trades we never received (for example during a
reconnect). `sequence` is NOT contiguous on this channel (it is shared with
order-book events), so it is stored but not used for gap detection.
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

import asyncpg
import redis
from kafka import KafkaProducer
from pydantic import AwareDatetime, BaseModel, Field, field_serializer
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from src.config import (
    COINBASE_WS_URL,
    KAFKA_PRODUCER_CONFIG,
    KAFKA_TOPIC_TRADES,
    LOG_LEVEL,
    POSTGRES_CONNECT_KWARGS,
    REDIS_HOST,
    REDIS_PORT,
)
from src.symbols import Symbol, fetch_symbols

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

HEALTHY_CONNECTION_SECONDS = 60   # a connection that lived this long resets the backoff
MAX_BACKOFF_SECONDS = 30.0
STATS_LOG_INTERVAL_SECONDS = 60


class Trade(BaseModel):
    trade_id: int = Field(gt=0)
    symbol: str
    price: Decimal = Field(gt=0)
    size: Decimal = Field(gt=0)
    side: Literal["buy", "sell"]
    sequence: int
    event_time: AwareDatetime
    ingest_time: AwareDatetime

    @field_serializer("event_time", "ingest_time")
    def _utc_z(self, dt: datetime) -> str:
        # Flink's Jackson Instant parser (Java 11 ISO_INSTANT) wants a trailing Z, not +00:00.
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class FatalFeedError(Exception):
    """Coinbase rejected the subscription (e.g. a delisted product). Reconnecting will not help."""


def parse_match(msg: dict, symbol_by_product: dict[str, str], ingest_time: datetime) -> Trade:
    """Map a Coinbase `match`/`last_match` message to a Trade. Raises ValueError if it is malformed."""
    symbol = symbol_by_product.get(msg.get("product_id"))
    if symbol is None:
        raise ValueError(f"untracked product: {msg.get('product_id')}")
    return Trade(
        trade_id=msg.get("trade_id"),
        symbol=symbol,
        price=msg.get("price"),
        size=msg.get("size"),
        side=msg.get("side"),
        sequence=msg.get("sequence"),
        event_time=msg.get("time"),
        ingest_time=ingest_time,
    )


class TradeGapTracker:
    """Counts trades missed per symbol from contiguous Coinbase trade_ids."""

    def __init__(self):
        self.last_trade_id: dict[str, int] = {}
        self.missed = 0

    def observe(self, symbol: str, trade_id: int) -> Optional[int]:
        """Record a trade_id. Returns None if it is not newer than the last one seen
        (a repeat or replay), otherwise the number of trades skipped since the previous one."""
        last = self.last_trade_id.get(symbol)
        if last is not None and trade_id <= last:
            return None
        self.last_trade_id[symbol] = trade_id
        if last is None:
            return 0
        gap = trade_id - last - 1
        self.missed += gap
        return gap


TRADES_PUBSUB_CHANNEL = "crypto:trades"
REDIS_WARN_INTERVAL_SECONDS = 30  # rate-limit "redis is down" log spam


class CoinbaseTradeProducer:
    def __init__(
        self, symbols: dict[str, Symbol], kafka_producer, topic: str,
        ws_url: str = COINBASE_WS_URL, redis_client=None,
    ):
        self.symbol_by_product = {s.coinbase_product: s.symbol for s in symbols.values()}
        self.kafka = kafka_producer
        self.topic = topic
        self.ws_url = ws_url
        self.redis_client = redis_client
        self.gaps = TradeGapTracker()
        self.stats = {"published": 0, "invalid": 0, "duplicates": 0, "send_errors": 0, "reconnects": 0}
        self._sleep = asyncio.sleep
        self._last_stats_log = time.monotonic()
        self._last_redis_warn = 0.0

    def handle_message(self, raw: str) -> None:
        """Validate one WebSocket frame and publish it if it is a new trade."""
        try:
            msg = json.loads(raw)
        except ValueError:
            self.stats["invalid"] += 1
            logger.warning("Dropping non-JSON frame: %.200s", raw)
            return

        kind = msg.get("type")
        if kind == "error":
            raise FatalFeedError(f"{msg.get('message')}: {msg.get('reason', '')}")
        if kind not in ("match", "last_match"):
            return

        try:
            trade = parse_match(msg, self.symbol_by_product, datetime.now(timezone.utc))
        except ValueError as e:
            self.stats["invalid"] += 1
            logger.warning("Dropping invalid trade message: %s", e)
            return

        gap = self.gaps.observe(trade.symbol, trade.trade_id)
        if gap is None:
            self.stats["duplicates"] += 1
            return
        if gap:
            logger.warning("%s: %d trades missed before trade_id %d", trade.symbol, gap, trade.trade_id)

        # ponytail: KafkaProducer.send can block the event loop briefly on first metadata fetch
        # or a full buffer; fine at ~10 trades/s, move to aiokafka if throughput grows 100x.
        self.kafka.send(self.topic, key=trade.symbol, value=trade.model_dump_json()).add_errback(
            self._on_send_error
        )
        self.stats["published"] += 1
        self._publish_trade(trade)

    def _publish_trade(self, trade: Trade) -> None:
        """Best-effort tick publish for the live line chart. Never blocks the Kafka path."""
        if self.redis_client is None:
            return
        try:
            self.redis_client.publish(TRADES_PUBSUB_CHANNEL, json.dumps({
                "symbol": trade.symbol,
                "price": float(trade.price),
                "time": trade.event_time.timestamp(),
            }))
        except Exception as e:
            now = time.monotonic()
            if now - self._last_redis_warn >= REDIS_WARN_INTERVAL_SECONDS:
                self._last_redis_warn = now
                logger.warning("Redis publish to %s failed: %s", TRADES_PUBSUB_CHANNEL, e)

    def _on_send_error(self, exc) -> None:
        self.stats["send_errors"] += 1
        logger.error("Kafka send failed: %s", exc)

    def _maybe_log_stats(self) -> None:
        now = time.monotonic()
        if now - self._last_stats_log >= STATS_LOG_INTERVAL_SECONDS:
            self._last_stats_log = now
            logger.info("stats %s missed_trades=%d", self.stats, self.gaps.missed)

    async def stream_once(self) -> None:
        """Connect, subscribe, and publish trades until the connection drops."""
        async with connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": sorted(self.symbol_by_product),
                "channels": ["matches"],
            }))
            logger.info("Subscribed to %d products on %s", len(self.symbol_by_product), self.ws_url)
            async for raw in ws:
                self.handle_message(raw)
                self._maybe_log_stats()

    async def run_forever(self) -> None:
        """Stream until a FatalFeedError; otherwise reconnect with capped exponential backoff plus jitter."""
        backoff = 1.0
        while True:
            started = time.monotonic()
            try:
                await self.stream_once()
                logger.warning("Coinbase closed the WebSocket")
            except (OSError, WebSocketException) as e:
                logger.warning("WebSocket error: %s", e)
            if time.monotonic() - started > HEALTHY_CONNECTION_SECONDS:
                backoff = 1.0
            self.stats["reconnects"] += 1
            await self._sleep(backoff + random.random())
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)


async def amain() -> None:
    conn = await asyncpg.connect(**POSTGRES_CONNECT_KWARGS)
    try:
        symbols = await fetch_symbols(conn)
    finally:
        await conn.close()

    kafka = KafkaProducer(**KAFKA_PRODUCER_CONFIG)
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    producer = CoinbaseTradeProducer(symbols, kafka, KAFKA_TOPIC_TRADES, redis_client=redis_client)
    try:
        await producer.run_forever()
    finally:
        kafka.flush(timeout=10)
        kafka.close()
        logger.info("Shutdown stats %s missed_trades=%d", producer.stats, producer.gaps.missed)


def main() -> None:
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        logger.info("Stopped by user")


if __name__ == "__main__":
    main()
