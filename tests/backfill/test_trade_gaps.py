from datetime import datetime, timezone

import httpx

from src.backfill.coinbase import CoinbaseRest
from src.backfill.trade_gaps import MAX_GAP, fetch_gap, repair_gaps, select_missing
from src.candle_sql import CANDLE_UPSERT_FROM_RAW_SQL


def trade(i, second=0, side="buy"):
    return {"trade_id": i, "side": side, "size": "0.5", "price": "100.0",
            "time": f"2026-09-27T07:50:{second:02d}.000000Z"}


def api_with_pages(pages):
    """pages: {after: (trades, cb_after)}; records every `after` requested."""
    requested = []

    def handler(request):
        after = int(request.url.params["after"])
        requested.append(after)
        trades, cursor = pages.get(after, ([], None))
        headers = {"cb-after": str(cursor)} if cursor is not None else {}
        return httpx.Response(200, json=trades, headers=headers)

    client = httpx.Client(base_url="https://api.test", transport=httpx.MockTransport(handler))
    return CoinbaseRest(client=client, sleep=lambda s: None, clock=lambda: 0.0), requested


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.calls.append(("execute", sql, params))

    def executemany(self, sql, rows):
        self.conn.calls.append(("executemany", sql, list(rows)))

    def fetchall(self):
        return self.conn.gaps


class FakeConn:
    def __init__(self, gaps):
        self.gaps, self.calls, self.commits = gaps, [], 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


def test_select_missing_keeps_only_ids_strictly_inside_the_gap():
    page = [trade(103), trade(102), trade(101), trade(100)]
    assert [t["trade_id"] for t in select_missing(page, prev_id=100, next_id=103)] == [102, 101]


def test_fetch_gap_pages_until_it_reaches_the_trade_before_the_gap():
    api, requested = api_with_pages({103: ([trade(102)], 102), 102: ([trade(101), trade(100)], 100)})
    assert [t["trade_id"] for t in fetch_gap(api, "BTC-USD", 100, 103)] == [102, 101]
    assert requested == [103, 102]


def test_fetch_gap_stops_on_empty_page():
    api, requested = api_with_pages({})
    assert fetch_gap(api, "BTC-USD", 100, 103) == []
    assert requested == [103]


def test_repair_inserts_missing_trades_and_recomputes_their_minute():
    api, _ = api_with_pages({103: ([trade(102, 5, "sell")], 102), 102: ([trade(101, 7), trade(100)], 100)})
    conn = FakeConn(gaps=[(1, "BTC", "BTC-USD", 100, 103)])
    report = repair_gaps(conn, api)
    assert report == {"gaps_found": 1, "gaps_repaired": 1, "gaps_skipped": 0,
                      "trades_inserted": 2, "minutes_recomputed": 1}
    inserted = next(rows for kind, _, rows in conn.calls if kind == "executemany")
    assert [(r[1], r[4], r[5]) for r in inserted] == [(102, "sell", None), (101, "buy", None)]  # side unchanged
    recomputes = [c for c in conn.calls if c[1] == CANDLE_UPSERT_FROM_RAW_SQL]
    minute = datetime(2026, 9, 27, 7, 50, tzinfo=timezone.utc)
    assert len(recomputes) == 1 and recomputes[0][2][0] == minute and recomputes[0][2][2] == "BTC"


def test_gap_larger_than_the_cap_is_skipped_without_any_request():
    api, requested = api_with_pages({})
    conn = FakeConn(gaps=[(1, "BTC", "BTC-USD", 100, 100 + MAX_GAP + 2)])
    report = repair_gaps(conn, api)
    assert report["gaps_skipped"] == 1 and report["trades_inserted"] == 0 and requested == []
