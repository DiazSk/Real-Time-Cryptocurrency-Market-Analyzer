"""Coinbase Exchange public REST client: throttled to a steady rate, retrying 429/5xx with backoff."""

import logging
import time

import httpx

API_URL = "https://api.exchange.coinbase.com"
RETRY_STATUSES = {429, 500, 502, 503, 504}
logger = logging.getLogger(__name__)


class CoinbaseRest:
    def __init__(self, client=None, rate_per_s=5.0, attempts=5, sleep=time.sleep, clock=time.monotonic):
        self.client = client or httpx.Client(base_url=API_URL, timeout=10)
        self.min_interval = 1.0 / rate_per_s
        self.attempts = attempts
        self.sleep, self.clock = sleep, clock
        self._last_request = float("-inf")

    def _get(self, path, params):
        error = None
        for attempt in range(self.attempts):
            wait = self._last_request + self.min_interval - self.clock()
            if wait > 0:
                self.sleep(wait)
            self._last_request = self.clock()
            try:
                response = self.client.get(path, params=params)
            except httpx.TransportError as e:
                error = e
            else:
                if response.status_code not in RETRY_STATUSES:
                    response.raise_for_status()  # other 4xx: a bug in our request, don't retry
                    return response
                error = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}", request=response.request, response=response)
            if attempt < self.attempts - 1:
                backoff = min(2 ** attempt, 30)
                logger.warning("Coinbase %s failed (%s); retrying in %ss", path, error, backoff)
                self.sleep(backoff)
        raise error

    def candles(self, product, start, end):
        """1-minute candles in [start, end] (both inclusive, <= 300 buckets), newest first."""
        params = {"granularity": 60, "start": start.isoformat(), "end": end.isoformat()}
        return self._get(f"/products/{product}/candles", params).json()

    def trades_page(self, product, after):
        """Up to 1000 trades with trade_id < after, newest first, plus the cursor for the next page."""
        response = self._get(f"/products/{product}/trades", {"limit": 1000, "after": after})
        cursor = response.headers.get("cb-after")
        return response.json(), int(cursor) if cursor else None
