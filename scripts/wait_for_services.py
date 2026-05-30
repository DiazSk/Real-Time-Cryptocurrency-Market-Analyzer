"""Poll infrastructure dependencies until they accept connections.

Usage: python scripts/wait_for_services.py {all|postgres|redis|kafka} \
           [--retries N] [--interval SECS]
"""

import argparse
import os
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


def _load_env() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().split("#", 1)[0].strip())


def _check(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _services(target: str) -> list[tuple[str, str, int]]:
    pg = ("postgres", os.environ.get("POSTGRES_HOST", "localhost"),
          int(os.environ.get("POSTGRES_PORT", "5433")))
    rd = ("redis", os.environ.get("REDIS_HOST", "localhost"),
          int(os.environ.get("REDIS_PORT", "6379")))
    kafka_bs = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").split(",")[0]
    kh, _, kp = kafka_bs.partition(":")
    kf = ("kafka", kh or "localhost", int(kp or "9092"))

    mapping = {"postgres": [pg], "redis": [rd], "kafka": [kf], "all": [pg, rd, kf]}
    if target not in mapping:
        sys.exit(f"Unknown target: {target}. Use one of {sorted(mapping)}.")
    return mapping[target]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["all", "postgres", "redis", "kafka"])
    parser.add_argument("--retries", type=int, default=30)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()

    _load_env()
    pending = _services(args.target)

    for attempt in range(1, args.retries + 1):
        still_pending = [s for s in pending if not _check(s[1], s[2])]
        ready = [s for s in pending if s not in still_pending]
        for name, host, port in ready:
            print(f"[ok] {name} ready at {host}:{port}")
        pending = still_pending
        if not pending:
            return 0
        names = ", ".join(s[0] for s in pending)
        print(f"[wait] attempt {attempt}/{args.retries}: waiting for {names}")
        time.sleep(args.interval)

    for name, host, port in pending:
        print(f"[fail] {name} not reachable at {host}:{port}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
