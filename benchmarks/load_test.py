"""Load test: REST latency, WebSocket fan-out, and freshness against the local stack.

Run with `make load-test` (full stack up, Flink job deployed, nothing on :8000).
"""

import argparse
import asyncio
import json
import subprocess
import time
from collections import Counter, defaultdict

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from benchmarks.common import API_URL, WS_URL, api_server, query, raise_fd_limit, run_conditions, utcnow, write_results
from benchmarks.stats import delivery_ratios, max_passing_step, percentiles, step_passed

ENDPOINTS = [
    "/api/v1/latest/all",
    "/api/v1/latest/BTC",
    "/api/v1/historical/BTC?interval=1m",
    "/api/v1/trades/BTC?seconds=60",
]


async def _rest_worker(client, deadline, samples, errors, sources):
    i = 0
    while time.monotonic() < deadline:
        path = ENDPOINTS[i % len(ENDPOINTS)]
        i += 1
        start = time.perf_counter()
        try:
            r = await client.get(path)
        except httpx.HTTPError:
            errors[path] += 1
            continue
        if r.is_success:
            samples[path].append((time.perf_counter() - start) * 1000)
            if path.startswith("/api/v1/latest"):
                sources[r.headers.get("x-data-source", "none")] += 1
        else:
            errors[path] += 1


async def rest_level(clients, seconds):
    samples, errors, sources = defaultdict(list), Counter(), Counter()
    limits = httpx.Limits(max_connections=clients, max_keepalive_connections=clients)
    async with httpx.AsyncClient(base_url=API_URL, timeout=5, limits=limits) as client:
        deadline = time.monotonic() + seconds
        await asyncio.gather(*(_rest_worker(client, deadline, samples, errors, sources) for _ in range(clients)))
    endpoints = {}
    for path in ENDPOINTS:
        ok = samples[path]
        total = len(ok) + errors[path]
        endpoints[path] = {
            "requests": total,
            "rps": total / seconds,
            "error_rate": errors[path] / total if total else None,
            "latency_ms": percentiles(ok),
        }
    all_ok = [ms for path in ENDPOINTS for ms in samples[path]]
    return {"clients": clients, "latency_ms": percentiles(all_ok), "endpoints": endpoints, "latest_sources": dict(sources)}


async def _read_trades(ws, deadline, lags_ms):
    count = 0
    while (left := deadline - time.monotonic()) > 0:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=left)
        except (asyncio.TimeoutError, ConnectionClosed):
            break
        msg = json.loads(raw)
        if msg.get("type") == "trade" and msg.get("time") is not None:
            count += 1
            lags_ms.append((time.time() - float(msg["time"])) * 1000)
    return count


async def ws_step(clients, seconds):
    conns = await asyncio.gather(
        *(connect(f"{WS_URL}/ws/prices/ALL", open_timeout=30) for _ in range(clients)), return_exceptions=True
    )
    ok = [c for c in conns if not isinstance(c, BaseException)]
    lags_ms = []
    deadline = time.monotonic() + seconds  # measure only once everyone is connected
    counts = list(await asyncio.gather(*(_read_trades(c, deadline, lags_ms) for c in ok)))
    await asyncio.gather(*(c.close() for c in ok), return_exceptions=True)
    counts += [0] * (clients - len(ok))  # a client that never connected received nothing
    ratios = delivery_ratios(counts)
    return {
        "clients": clients,
        "connected": len(ok),
        "max_trades": max(counts, default=0),
        "min_delivery_ratio": min(ratios, default=0.0),
        "passed": step_passed(counts),
        "lag_ms": percentiles(lags_ms),
    }


async def ingestion_lag(since):
    rows = await query(
        """SELECT percentile_cont(ARRAY[0.5, 0.95]) WITHIN GROUP
                  (ORDER BY extract(epoch FROM ingest_time - event_time) * 1000) AS p
           FROM raw_trades WHERE ingest_time >= $1""",
        since,
    )
    p = rows[0]["p"]
    return {"p50": p[0], "p95": p[1]} if p else {"p50": None, "p95": None}


def clock_offset_seconds():
    """Local clock minus NTP time via macOS sntp, or None when it can't be measured."""
    try:
        out = subprocess.run(["sntp", "time.apple.com"], capture_output=True, text=True, timeout=10).stdout
        return float(out.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


async def run(args):
    started = utcnow()
    rest = []
    for level in args.levels:
        print(f"REST: {level} clients for {args.rest_seconds}s")
        rest.append(await rest_level(level, args.rest_seconds))
    ws = []
    for step in args.ws_steps:
        print(f"WS: {step} clients for {args.ws_seconds}s")
        ws.append(await ws_step(step, args.ws_seconds))
    return {
        "started": started,
        "conditions": run_conditions() | {"clock_offset_seconds": clock_offset_seconds()},
        "rest": rest,
        "websocket": {"steps": ws, "max_clients_at_99pct_delivery": max_passing_step(ws)},
        "freshness": {
            "ingestion_lag_ms": await ingestion_lag(started),
            "exchange_to_client_lag_ms": ws[0]["lag_ms"] if ws else None,
        },
        "caveats": [
            "Load generator and stack share one machine; numbers are a lower bound.",
            "API runs as a single uvicorn process.",
            "Exchange-to-client lag includes Coinbase network delay and local clock offset.",
            "Trade frames take producer -> Redis -> API and skip Kafka/Flink.",
        ],
    }


def _fmt(v):
    return "-" if v is None else f"{v:.1f}"


def summarize(result):
    print("\nREST (all endpoints)      p50     p95     p99   ms")
    for level in result["rest"]:
        lat = level["latency_ms"]
        print(f"  {level['clients']:>3} clients         {_fmt(lat['p50']):>7} {_fmt(lat['p95']):>7} {_fmt(lat['p99']):>7}")
    print("\nWebSocket  clients  connected  min delivery  p95 lag ms  passed")
    for s in result["websocket"]["steps"]:
        print(f"           {s['clients']:>7}  {s['connected']:>9}  {s['min_delivery_ratio']:>12.3f}  "
              f"{_fmt(s['lag_ms']['p95']):>10}  {s['passed']}")
    print(f"\nMax clients at >=99% delivery: {result['websocket']['max_clients_at_99pct_delivery']}")
    lag = result["freshness"]["ingestion_lag_ms"]
    print(f"Ingestion lag p50/p95 ms: {_fmt(lag['p50'])} / {_fmt(lag['p95'])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rest-seconds", type=int, default=60)
    parser.add_argument("--ws-seconds", type=int, default=60)
    parser.add_argument("--levels", type=lambda s: [int(x) for x in s.split(",")], default=[10, 50, 100])
    parser.add_argument("--ws-steps", type=lambda s: [int(x) for x in s.split(",")], default=[25, 50, 100, 200, 400])
    parser.add_argument("--no-save", action="store_true", help="smoke runs: print only, don't write results")
    args = parser.parse_args()
    raise_fd_limit()
    with api_server(reuse=False):
        result = asyncio.run(run(args))
    summarize(result)
    if not args.no_save:
        print(f"\nWrote {write_results('load', result)}")


if __name__ == "__main__":
    main()
