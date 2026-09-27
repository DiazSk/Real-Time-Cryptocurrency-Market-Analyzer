"""Shared plumbing for the benchmark scripts: DB access, API launch, results files."""

import json
import os
import platform
import resource
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx

from src.config import POSTGRES_CONNECT_KWARGS

API_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "benchmarks" / "results"


def utcnow():
    return datetime.now(timezone.utc)


async def query(sql, *args):
    """One short-lived connection per call, so a Postgres restart can't strand the script."""
    conn = await asyncpg.connect(**POSTGRES_CONNECT_KWARGS, timeout=5)
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def raise_fd_limit():
    """400 WebSocket clients need more than macOS's default 256 open files (inherited by the API we launch)."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = 4096 if hard == resource.RLIM_INFINITY else min(4096, hard)
    if soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))


def _port_in_use(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


@contextmanager
def api_server(reuse):
    """Yield with a healthy API on :8000.

    reuse=True accepts an API that is already running (chaos test).
    reuse=False insists on launching a fresh single-process API without --reload (load test).
    """
    if _port_in_use(8000):
        if reuse:
            yield
            return
        sys.exit("Port 8000 is in use (probably `make api`, which runs with --reload). Stop it and rerun.")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", "8000", "--log-level", "warning"],
        cwd=ROOT,
    )
    try:
        for _ in range(60):
            if proc.poll() is not None:
                sys.exit("The API exited during startup; run `make api` to see why.")
            try:
                if httpx.get(f"{API_URL}/health", timeout=1).is_success:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            sys.exit("The API did not become healthy within 30 s.")
        yield
    finally:
        proc.terminate()
        proc.wait(10)


def run_conditions():
    """Where the numbers came from; stored in every results file."""
    docker_mem = subprocess.run(
        ["docker", "info", "--format", "{{.MemTotal}}"], capture_output=True, text=True
    ).stdout.strip()
    return {
        "host": platform.platform(),
        "cpu_count": os.cpu_count(),
        "docker_mem_bytes": int(docker_mem) if docker_mem.isdigit() else None,
        "api_workers": 1,
        "load_generator": "same machine as the stack",
    }


def write_results(kind, payload):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{utcnow():%Y-%m-%d}-{kind}.json"
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return path
