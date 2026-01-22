#!/usr/bin/env python3
"""
Cross-platform service health check utility.
Waits for Docker services to be healthy before proceeding.

Usage:
    python scripts/wait_for_services.py [service] [--retries N] [--interval N]

Examples:
    python scripts/wait_for_services.py all
    python scripts/wait_for_services.py kafka --retries 30 --interval 5
    python scripts/wait_for_services.py postgres redis
"""

import argparse
import subprocess
import sys
import time
from typing import List, Optional


def run_command(cmd: List[str], capture: bool = True) -> tuple:
    """Run a command and return (success, output)."""
    try:
        result = subprocess.run(cmd, capture_output=capture, text=True, timeout=30)
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except FileNotFoundError:
        return False, "Docker not found"
    except Exception as e:
        return False, str(e)


def check_docker_running() -> bool:
    """Check if Docker daemon is running."""
    success, _ = run_command(["docker", "info"])
    return success


def get_container_health(container: str) -> Optional[str]:
    """Get health status of a container."""
    success, output = run_command(
        ["docker", "inspect", "--format", "{{.State.Health.Status}}", container]
    )
    if success and output:
        return output
    return None


def is_container_running(container: str) -> bool:
    """Check if container is running."""
    success, output = run_command(
        ["docker", "inspect", "--format", "{{.State.Running}}", container]
    )
    return success and output.lower() == "true"


def check_kafka_ready() -> bool:
    """Additional check for Kafka topic availability."""
    success, _ = run_command(
        [
            "docker",
            "exec",
            "kafka",
            "kafka-topics",
            "--bootstrap-server",
            "localhost:9092",
            "--list",
        ]
    )
    return success


def check_postgres_ready() -> bool:
    """Additional check for PostgreSQL accepting connections."""
    success, _ = run_command(
        [
            "docker",
            "exec",
            "postgres",
            "pg_isready",
            "-U",
            "crypto_user",
            "-d",
            "crypto_db",
        ]
    )
    return success


def check_redis_ready() -> bool:
    """Additional check for Redis responding to PING."""
    success, output = run_command(["docker", "exec", "redis", "redis-cli", "ping"])
    return success and "PONG" in output.upper()


def check_flink_ready() -> bool:
    """Check if Flink JobManager API is responding."""
    try:
        import urllib.request

        with urllib.request.urlopen(
            "http://localhost:8082/overview", timeout=5
        ) as response:
            return response.status == 200
    except Exception:
        return False


SERVICE_CHECKS = {
    "zookeeper": {
        "container": "zookeeper",
        "friendly_name": "Zookeeper",
        "extra_check": None,
    },
    "kafka": {
        "container": "kafka",
        "friendly_name": "Apache Kafka",
        "extra_check": check_kafka_ready,
    },
    "postgres": {
        "container": "postgres",
        "friendly_name": "PostgreSQL",
        "extra_check": check_postgres_ready,
    },
    "redis": {
        "container": "redis",
        "friendly_name": "Redis",
        "extra_check": check_redis_ready,
    },
    "flink": {
        "container": "flink-jobmanager",
        "friendly_name": "Flink JobManager",
        "extra_check": check_flink_ready,
    },
}


def wait_for_service(service: str, max_retries: int, interval: int) -> bool:
    """Wait for a service to become healthy."""
    if service not in SERVICE_CHECKS:
        print(f"[ERROR] Unknown service: {service}")
        return False

    config = SERVICE_CHECKS[service]
    container = config["container"]
    friendly_name = config["friendly_name"]
    extra_check = config["extra_check"]

    print(f"[INFO] Waiting for {friendly_name} ({container})...")

    for attempt in range(1, max_retries + 1):
        # First check if container is running
        if not is_container_running(container):
            print(
                f"[WAIT] {friendly_name} container not running... (attempt {attempt}/{max_retries})"
            )
            time.sleep(interval)
            continue

        # Check health status
        health = get_container_health(container)

        if health == "healthy":
            # Run extra check if defined
            if extra_check:
                if extra_check():
                    print(f"[OK] {friendly_name} is healthy and ready!")
                    return True
                else:
                    print(
                        f"[WAIT] {friendly_name} container healthy but service not ready... (attempt {attempt}/{max_retries})"
                    )
            else:
                print(f"[OK] {friendly_name} is healthy!")
                return True
        elif health is None:
            # No healthcheck defined, just check if running and extra check passes
            if extra_check:
                if extra_check():
                    print(f"[OK] {friendly_name} is ready!")
                    return True
            else:
                print(f"[OK] {friendly_name} is running (no healthcheck defined)")
                return True
        else:
            print(
                f"[WAIT] {friendly_name} not ready yet (status: {health})... (attempt {attempt}/{max_retries})"
            )

        time.sleep(interval)

    print(
        f"[ERROR] {friendly_name} failed to become healthy after {max_retries} attempts"
    )
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Wait for Docker services to be healthy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Services:
  all        - Check all core services (zookeeper, kafka, postgres, redis)
  zookeeper  - Check Zookeeper only
  kafka      - Check Kafka only  
  postgres   - Check PostgreSQL only
  redis      - Check Redis only
  flink      - Check Flink JobManager only

Examples:
  python scripts/wait_for_services.py all
  python scripts/wait_for_services.py kafka postgres
  python scripts/wait_for_services.py kafka --retries 60 --interval 2
        """,
    )
    parser.add_argument(
        "services", nargs="*", default=["all"], help="Services to check (default: all)"
    )
    parser.add_argument(
        "--retries",
        "-r",
        type=int,
        default=30,
        help="Maximum number of retries (default: 30)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=5,
        help="Seconds between retries (default: 5)",
    )

    args = parser.parse_args()

    print()
    print("=" * 40)
    print("  Service Health Check")
    print("=" * 40)
    print()

    # Check if Docker is running
    if not check_docker_running():
        print("[ERROR] Docker is not running!")
        print("Please start Docker Desktop and try again.")
        sys.exit(1)

    # Determine which services to check
    if "all" in args.services:
        services = ["zookeeper", "kafka", "postgres", "redis"]
    else:
        services = args.services

    # Check each service
    all_healthy = True
    for service in services:
        if not wait_for_service(service, args.retries, args.interval):
            all_healthy = False

    print()
    if all_healthy:
        print("=" * 40)
        print("  All Services Are Healthy!")
        print("=" * 40)
        sys.exit(0)
    else:
        print("=" * 40)
        print("  Some Services Failed Health Check")
        print("=" * 40)
        sys.exit(1)


if __name__ == "__main__":
    main()
