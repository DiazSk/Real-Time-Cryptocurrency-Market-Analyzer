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
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

CHANNELS = ("crypto:updates", "crypto:trades")

Handler = Callable[[str, dict], Awaitable[None]]


class PubSubDispatcher:
    """Runs the subscribe loop as a single asyncio task and fans out messages."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._handlers: list[Handler] = []

    def add_handler(self, handler: Handler) -> None:
        self._handlers.append(handler)

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, redis_client) -> None:
        """Start the listener task. A no-op if one is already running."""
        if self.is_running:
            return
        self._task = asyncio.create_task(self._listen(redis_client), name="redis-pubsub-listener")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _listen(self, redis_client) -> None:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(*CHANNELS)
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
            await pubsub.unsubscribe(*CHANNELS)
            await pubsub.aclose()


# Module-level singleton: handlers register on it at import time (see websocket.py),
# database.lifespan starts/stops it against the real app.state.redis client.
pubsub_dispatcher = PubSubDispatcher()
