from datetime import datetime

import httpx
import pytest

from src.backfill.coinbase import CoinbaseRest


def make_api(handler, **kw):
    sleeps = []
    api = CoinbaseRest(
        client=httpx.Client(base_url="https://api.test", transport=httpx.MockTransport(handler)),
        sleep=sleeps.append, clock=lambda: 0.0, **kw,
    )
    return api, sleeps


def test_retries_429_then_succeeds():
    calls = []

    def handler(request):
        calls.append(request.url.params["after"])
        return httpx.Response(429) if len(calls) == 1 else httpx.Response(
            200, json=[{"trade_id": 9}], headers={"cb-after": "9"})

    api, sleeps = make_api(handler)
    page, cursor = api.trades_page("BTC-USD", after=10)
    assert page == [{"trade_id": 9}] and cursor == 9
    assert len(calls) == 2 and 1 in sleeps  # 1 s backoff after the 429


def test_other_4xx_is_raised_without_retry():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(400, json={"message": "bad"})

    api, _ = make_api(handler)
    with pytest.raises(httpx.HTTPStatusError):
        api.candles("BTC-USD", datetime(2026, 9, 1), datetime(2026, 9, 1))
    assert len(calls) == 1


def test_gives_up_after_the_attempt_budget():
    api, _ = make_api(lambda request: httpx.Response(503), attempts=3)
    with pytest.raises(httpx.HTTPStatusError):
        api.trades_page("BTC-USD", after=10)
