"""
Redis Pub/Sub -> WebSocket bridge.

One asyncio task (started/cancelled by database.lifespan) reads both
`crypto:updates` (candles) and `crypto:trades` (tick stream) off
`app.state.redis.pubsub()` and dispatches (channel, data) to registered
handlers. The previous design ran a background thread that opened a brand
new event loop per message and called websocket.send_json() from it — that
loop is not the one driving the WebSocket, and it broke down at roughly
10 messages/second.
"""

import asyncio
import json
import logging
import time
from typing import Awaitable, Callable

import redis.exceptions

logger = logging.getLogger(__name__)

CHANNELS = ("crypto:updates", "crypto:trades")

Handler = Callable[[str, dict], Awaitable[None]]

RECONNECT_BASE_DELAY_SECONDS = 1.0
RECONNECT_MAX_DELAY_SECONDS = 30.0
HEALTHY_CONNECTION_SECONDS = 60  # a subscription alive this long resets the backoff

# Errors a dropped Redis connection can surface as. redis-py's ConnectionError and
# TimeoutError derive from RedisError, not the builtins, so both families are listed;
# missing them let a `docker stop redis` kill the listener task for good.
REDIS_CONNECTION_ERRORS = (
    redis.exceptions.ConnectionError,
    redis.exceptions.TimeoutError,
    ConnectionError,
    TimeoutError,
    OSError,
)


class PubSubDispatcher:
    """Runs the subscribe loop as a single, self-reconnecting asyncio task and fans
    out messages to registered handlers. A dropped Redis connection is retried with
    capped exponential backoff (1s -> 30s, reset after a healthy stretch) rather than
    silently killing the task forever."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._handlers: list[Handler] = []
        self._connected = False
        self._sleep = asyncio.sleep  # overridable in tests

    def add_handler(self, handler: Handler) -> None:
        self._handlers.append(handler)

    @property
    def is_running(self) -> bool:
        """True only while actually subscribed — not merely while the task is alive
        (e.g. it's still False during a reconnect backoff sleep)."""
        return self._connected

    def start(self, redis_client) -> None:
        """Start the supervising task. A no-op if one is already active."""
        if self._task is not None and not self._task.done():
            return
        self._connected = False
        self._task = asyncio.create_task(self._supervise(redis_client), name="redis-pubsub-listener")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self._connected = False

    async def _supervise(self, redis_client) -> None:
        """Reconnect loop: run one subscription until it drops, then retry with
        backoff. CancelledError (from stop()) is not caught here, so it propagates
        straight out and the task exits cleanly."""
        delay = RECONNECT_BASE_DELAY_SECONDS
        try:
            while True:
                started = time.monotonic()
                try:
                    await self._listen_once(redis_client)
                except REDIS_CONNECTION_ERRORS as e:
                    logger.warning("Redis pub/sub connection lost, reconnecting: %s", e)
                if time.monotonic() - started > HEALTHY_CONNECTION_SECONDS:
                    delay = RECONNECT_BASE_DELAY_SECONDS
                await self._sleep(delay)
                delay = min(delay * 2, RECONNECT_MAX_DELAY_SECONDS)
        finally:
            self._connected = False

    async def _listen_once(self, redis_client) -> None:
        """One subscription attempt: subscribe, then dispatch messages until the
        connection drops or this task is cancelled."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(*CHANNELS)
        self._connected = True
        logger.info("Subscribed to %s", ", ".join(CHANNELS))
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                channel = message["channel"]
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error("Bad pub/sub payload on %s: %s", channel, e)
                    continue
                for handler in self._handlers:
                    try:
                        await handler(channel, data)
                    except Exception as e:
                        logger.error("pub/sub handler error on %s: %s", channel, e)
        finally:
            self._connected = False
            try:
                await pubsub.unsubscribe(*CHANNELS)
                await pubsub.aclose()
            except Exception as e:
                logger.debug("Error tearing down pub/sub connection: %s", e)


# Module-level singleton: handlers register on it at import time (see websocket.py),
# database.lifespan starts/stops it against the real app.state.redis client.
pubsub_dispatcher = PubSubDispatcher()
