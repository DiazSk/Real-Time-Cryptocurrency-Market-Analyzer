"""Chaos test: inject 5 failures and measure recovery time, lost trades and candle consistency.

Run with `make chaos-test` against the full local stack (Flink job deployed, producer running).
"""

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import timedelta

import asyncpg
import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from benchmarks.common import API_URL, ROOT, WS_URL, api_server, query, run_conditions, utcnow, write_results
from benchmarks.stats import parse_send_errors, send_errors_delta
from src.config import POSTGRES_CONNECT_KWARGS

SCENARIOS = ["taskmanager", "kafka", "postgres", "redis", "producer"]
PRODUCER = "src.producers.coinbase_trades_producer"
PRODUCER_LOG = ROOT / "logs" / "producer.log"
BASELINE_S, OUTAGE_S, RECOVERY_TIMEOUT_S, SETTLE_S = 60, 30, 300, 60 + 70
CHECKS_SQL = (ROOT / "benchmarks" / "checks.sql").read_text()

stopped_containers = set()  # restarted on exit, even after Ctrl-C
producer_killed = False


def docker(*args):
    subprocess.run(["docker", *args], check=True, capture_output=True, text=True)


def assert_local_stack():
    out = subprocess.run(["docker", "port", "postgres", "5432"], capture_output=True, text=True).stdout
    if ":5433" not in out:
        sys.exit("Refusing to run: the `postgres` container is not the local compose stack on host port 5433.")


def send_errors_now():
    return parse_send_errors(PRODUCER_LOG.read_text(errors="replace")) if PRODUCER_LOG.exists() else None


def producer_pids():
    out = subprocess.run(["pgrep", "-f", PRODUCER], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if int(p) != os.getpid()]


def start_producer():
    PRODUCER_LOG.parent.mkdir(exist_ok=True)
    log = open(PRODUCER_LOG, "a")
    subprocess.Popen([sys.executable, "-m", PRODUCER], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                     start_new_session=True)  # outlives this script, like start_pipeline.sh


def restart_producer():
    global producer_killed
    pids = producer_pids()
    if not pids:
        raise RuntimeError("producer is not running; start it with scripts/start_pipeline.sh")
    for pid in pids:
        os.kill(pid, signal.SIGTERM)
    producer_killed = True
    for _ in range(20):
        if not producer_pids():
            break
        time.sleep(0.5)
    else:
        for pid in producer_pids():
            os.kill(pid, signal.SIGKILL)
    start_producer()
    producer_killed = False


def flink_running():
    try:
        jobs = httpx.get("http://localhost:8082/jobs/overview", timeout=3).json()["jobs"]
        return any(j["state"] == "RUNNING" for j in jobs)
    except (httpx.HTTPError, KeyError, ValueError):
        return False


async def rows_since(ts):
    try:
        rows = await query("SELECT EXISTS (SELECT 1 FROM raw_trades WHERE ingest_time > $1) AS e", ts)
        return rows[0]["e"]
    except (OSError, asyncpg.PostgresError, asyncio.TimeoutError):
        return False  # Postgres is down or restarting


async def wait_recovered(t_cleared):
    """First moment a trade ingested after the fault was cleared is in raw_trades (the whole path works)."""
    deadline = time.monotonic() + RECOVERY_TIMEOUT_S
    while time.monotonic() < deadline:
        if await rows_since(t_cleared):
            return utcnow()
        await asyncio.sleep(1)
    return None


async def probe_latest(stop):
    ok = total = 0
    sources = Counter()
    async with httpx.AsyncClient(base_url=API_URL, timeout=2) as client:
        while not stop.is_set():
            total += 1
            try:
                r = await client.get("/api/v1/latest/BTC")
                if r.status_code == 200:
                    ok += 1
                    sources[r.headers.get("x-data-source", "none")] += 1
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)
    return {"requests": total, "availability": ok / total if total else None, "sources": dict(sources)}


async def first_trade_after(cleared, cleared_at):
    """Seconds from `docker start redis` to the first WS trade frame for a trade made after it."""
    async with connect(f"{WS_URL}/ws/prices/ALL", open_timeout=30) as ws:
        await cleared.wait()
        deadline = time.monotonic() + RECOVERY_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic()))
            except (asyncio.TimeoutError, ConnectionClosed):
                return None
            if msg.get("type") == "trade" and float(msg.get("time") or 0) > cleared_at[0]:
                return time.time() - cleared_at[0]
    return None


async def run_scenario(name):
    if not await rows_since(utcnow() - timedelta(seconds=30)):
        raise RuntimeError("no trades in the last 30 s; the pipeline isn't flowing")
    print(f"[{name}] baseline {BASELINE_S}s")
    await asyncio.sleep(BASELINE_S)
    errors_before = send_errors_now()
    extra, outage = {}, 0
    t_fault = utcnow()
    print(f"[{name}] fault")
    if name == "taskmanager":
        docker("restart", "flink-taskmanager")
    elif name == "kafka":
        docker("restart", "kafka")
    elif name == "postgres":
        docker("stop", "postgres")
        stopped_containers.add("postgres")
        await asyncio.sleep(OUTAGE_S)
        docker("start", "postgres")
        stopped_containers.discard("postgres")
        outage = OUTAGE_S
    elif name == "redis":
        stop_probe, cleared, cleared_at = asyncio.Event(), asyncio.Event(), [0.0]
        probe = asyncio.create_task(probe_latest(stop_probe))
        ws_task = asyncio.create_task(first_trade_after(cleared, cleared_at))
        await asyncio.sleep(2)  # let the WS client connect before Redis goes away
        docker("stop", "redis")
        stopped_containers.add("redis")
        await asyncio.sleep(OUTAGE_S)
        docker("start", "redis")
        stopped_containers.discard("redis")
        cleared_at[0] = time.time()
        cleared.set()
        outage = OUTAGE_S  # probe and WS tasks keep running; collected after the settle below
    elif name == "producer":
        restart_producer()
    t_cleared = utcnow()

    t_recovered = await wait_recovered(t_cleared)
    print(f"[{name}] recovered={t_recovered is not None}; settling {SETTLE_S}s")
    flink = flink_running()
    await asyncio.sleep(SETTLE_S)
    if name == "redis":
        stop_probe.set()
        extra["api_probe"] = await probe
        extra["ws_trade_resumed_seconds"] = await ws_task

    t0 = t_fault - timedelta(seconds=60)
    t1 = (t_recovered or utcnow()) + timedelta(seconds=60)
    gaps = await query("SELECT * FROM chaos_gaps($1, $2)", t0, t1)
    mismatches = await query("SELECT * FROM chaos_candle_mismatches($1, $2)", t0, t1)
    return {
        "name": name,
        "t_fault": t_fault,
        "t_cleared": t_cleared,
        "t_recovered": t_recovered,
        "recovered": t_recovered is not None,
        "recovery_seconds": (t_recovered - t_fault).total_seconds() if t_recovered else None,
        "outage_seconds": outage,
        "gaps_by_symbol": {r["symbol"]: r["gaps"] for r in gaps},
        "gaps_total": sum(r["gaps"] for r in gaps),
        "candle_mismatches": [dict(r) for r in mismatches],
        "send_errors_delta": send_errors_delta(errors_before, send_errors_now()),
        "flink_running": flink,
    } | extra


async def run(names):
    conn = await asyncpg.connect(**POSTGRES_CONNECT_KWARGS)
    try:
        await conn.execute(CHECKS_SQL)
    finally:
        await conn.close()
    results = []
    for name in names:
        try:
            results.append(await run_scenario(name))
        except Exception as e:  # record and move on; restore happens in main()'s finally
            print(f"[{name}] ERROR {e}")
            results.append({"name": name, "error": str(e), "recovered": False})
            for c in list(stopped_containers):
                docker("start", c)
                stopped_containers.discard(c)
    return results


def summarize(results):
    print("\nscenario      recovered  recovery s  gaps  candle mismatches  send_errors")
    for r in results:
        rec = "-" if r.get("recovery_seconds") is None else f"{r['recovery_seconds']:.1f}"
        print(f"{r['name']:<13} {str(r.get('recovered')):<10} {rec:>10}  {r.get('gaps_total', '-'):>4}  "
              f"{len(r.get('candle_mismatches', [])):>17}  {r.get('send_errors_delta', '-')}")
        if "api_probe" in r:
            print(f"              API availability {r['api_probe']['availability']}, sources {r['api_probe']['sources']}, "
                  f"WS trades resumed after {r['ws_trade_resumed_seconds']}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=SCENARIOS, action="append", help="run just these scenarios")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    assert_local_stack()
    started = utcnow()
    try:
        with api_server(reuse=True):
            results = asyncio.run(run(args.only or SCENARIOS))
    finally:
        for c in list(stopped_containers):
            print(f"restoring {c}")
            docker("start", c)
        if producer_killed and not producer_pids():
            print("restarting the producer")
            start_producer()
    summarize(results)
    if not args.no_save:
        path = write_results("chaos", {"started": started, "conditions": run_conditions(), "scenarios": results})
        print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
