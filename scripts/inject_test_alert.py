"""
Publish a synthetic trade stream for the inactive TEST symbol that ends in a sharp jump,
so the z-score detector must raise exactly one alert.

It runs in real time (~35 minutes) because Flink uses event time and the detector needs
30 one-minute returns of warm-up. Trades are stamped "now", so they flow through the
same watermarks as live Coinbase trades.

Prerequisite (once per database):
  INSERT INTO cryptocurrencies (symbol, name, coingecko_id, coinbase_product, is_active)
  VALUES ('TEST', 'Test Coin', 'test-coin', 'TEST-USD', false) ON CONFLICT DO NOTHING;

Run: PYTHONPATH=. venv/bin/python scripts/inject_test_alert.py
"""

import json
import math
import time
from datetime import datetime, timezone

from kafka import KafkaProducer

from src.config import KAFKA_PRODUCER_CONFIG, KAFKA_TOPIC_TRADES

CALM_MINUTES = 33          # minute 0 anchors; minutes 1-32 give 32 warm-up returns (>= 30)
JUMP_MINUTE = CALM_MINUTES
TOTAL_MINUTES = CALM_MINUTES + 2   # + the jump minute + one trailing minute to close its window
TRADES_PER_MINUTE = 12     # one every 5 s; the detector needs >= 5 per candle


def utc_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> None:
    producer = KafkaProducer(**KAFKA_PRODUCER_CONFIG)
    trade_id = int(time.time()) * 1000   # stays above ids from earlier runs (DedupByTradeId state)
    price = 100.0
    start = math.ceil(time.time() / 60) * 60   # next minute boundary
    time.sleep(start - time.time())

    for minute in range(TOTAL_MINUTES):
        if minute == JUMP_MINUTE:
            price *= math.exp(0.05)
        elif minute > 0:
            price *= math.exp(0.001 if minute % 2 else -0.001)
        for i in range(TRADES_PER_MINUTE):
            time.sleep(max(0.0, start + minute * 60 + i * 5 - time.time()))
            trade_id += 1
            now = utc_z(datetime.now(timezone.utc))
            producer.send(KAFKA_TOPIC_TRADES, key="TEST", value=json.dumps({
                "trade_id": trade_id, "symbol": "TEST", "price": f"{price:.8f}", "size": "0.01",
                "side": "buy", "sequence": trade_id, "event_time": now, "ingest_time": now,
            }))
        print(f"minute {minute:2d}/{TOTAL_MINUTES - 1}: price {price:.6f}", flush=True)

    producer.flush()
    print("done: expect exactly one PRICE_SPIKE alert for TEST")


if __name__ == "__main__":
    main()
