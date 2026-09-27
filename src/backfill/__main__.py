"""python -m src.backfill [candles|gaps|all] — see src/backfill/candles.py and trade_gaps.py."""

import argparse
import logging

import psycopg2

from src.backfill.candles import backfill_candles
from src.backfill.coinbase import CoinbaseRest
from src.backfill.trade_gaps import repair_gaps
from src.config import LOG_LEVEL, POSTGRES_CONNECT_KWARGS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("what", nargs="?", choices=["candles", "gaps", "all"], default="all")
    args = parser.parse_args(argv)
    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request drowns the per-symbol summary
    conn = psycopg2.connect(**POSTGRES_CONNECT_KWARGS)
    api = CoinbaseRest()
    try:
        if args.what in ("candles", "all"):
            print("candles loaded:", backfill_candles(conn, api))
        if args.what in ("gaps", "all"):
            print("trade gaps:", repair_gaps(conn, api))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
