from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.backfill.candles import HISTORY, candle_start, candle_windows, parse_candle

T = datetime(2026, 9, 20, tzinfo=timezone.utc)
M = timedelta(minutes=1)


def test_windows_cover_300_buckets_each_with_inclusive_ends():
    assert list(candle_windows(T, T + 600 * M)) == [(T, T + 299 * M), (T + 300 * M, T + 599 * M)]


def test_windows_clip_the_last_window_to_end():
    windows = list(candle_windows(T, T + 650 * M))
    assert len(windows) == 3 and windows[-1] == (T + 600 * M, T + 650 * M)


def test_no_windows_when_start_is_not_before_end():
    assert list(candle_windows(T, T)) == []


def test_resume_starts_one_minute_before_last_bucket():
    assert candle_start(T, T + 60 * M) == T - M


def test_first_run_starts_90_days_back():
    assert candle_start(None, T) == T - HISTORY


def test_parse_candle_maps_coinbase_column_order():
    # Coinbase rows are [time, low, high, open, close, volume]
    row = [int(T.timestamp()), 99.5, 101.25, 100, 101, 2.5]
    assert parse_candle(row) == (T, Decimal("100"), Decimal("101.25"), Decimal("99.5"), Decimal("101"), Decimal("2.5"))
