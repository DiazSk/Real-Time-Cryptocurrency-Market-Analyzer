#!/usr/bin/env python3
"""
Cross-platform launcher for Real-Time Cryptocurrency Market Analyzer.

Usage:
    python run.py [command] [options]

Commands:
    start       - Start Docker services (full or lite mode)
    stop        - Stop Docker services
    producer    - Run the crypto price producer
    api         - Run the FastAPI server
    dashboard   - Run the Streamlit dashboard
    consumer    - Run the simple Python consumer (for lite mode)
    status      - Check status of all services
    logs        - View logs for a service
    health      - Check health of Docker services

Examples:
    python run.py start                 # Start full mode
    python run.py start --lite          # Start lite mode (low RAM)
    python run.py producer
    python run.py api
    python run.py dashboard
    python run.py status
    python run.py logs kafka
"""

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


# Get project root directory
PROJECT_ROOT = Path(__file__).parent.absolute()

# Detect OS
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"


def get_python_executable():
    """Get the correct Python executable path."""
    venv_path = PROJECT_ROOT / "venv"

    if IS_WINDOWS:
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        python_path = venv_path / "bin" / "python"

    if python_path.exists():
        return str(python_path)

    # Fall back to system Python
    return sys.executable


def get_venv_activate_command():
    """Get the venv activation command for the current OS."""
    venv_path = PROJECT_ROOT / "venv"

    if IS_WINDOWS:
        return str(venv_path / "Scripts" / "activate.bat")
    else:
        return f"source {venv_path / 'bin' / 'activate'}"


def check_venv_exists():
    """Check if virtual environment exists."""
    venv_path = PROJECT_ROOT / "venv"
    return venv_path.exists()


def check_docker_running():
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def run_command(cmd, cwd=None, env=None, check=True):
    """Run a command and handle errors."""
    try:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        result = subprocess.run(
            cmd, cwd=cwd or PROJECT_ROOT, env=merged_env, check=check
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"[ERROR] Command not found: {cmd[0]}")
        return False


def wait_for_services(services="all", retries=30, interval=5):
    """Wait for Docker services to be healthy."""
    python = get_python_executable()
    script = PROJECT_ROOT / "scripts" / "wait_for_services.py"

    cmd = [
        python,
        str(script),
        services,
        "--retries",
        str(retries),
        "--interval",
        str(interval),
    ]
    return run_command(cmd, check=False)


def cmd_start(args):
    """Start Docker services."""
    print()
    print("=" * 50)
    print("  Starting Crypto Market Analyzer")
    print("=" * 50)
    print()

    if not check_docker_running():
        print("[ERROR] Docker is not running!")
        print("Please start Docker Desktop and try again.")
        return False

    compose_file = "docker-compose-lite.yml" if args.lite else "docker-compose.yml"
    mode = "Lite" if args.lite else "Full"

    print(f"[INFO] Starting in {mode} Mode...")
    if args.lite:
        print("[INFO] Lite mode skips Flink for systems with <16GB RAM")
    print()

    # Stop any existing containers
    print("[INFO] Stopping any existing containers...")
    run_command(["docker-compose", "-f", compose_file, "down"], check=False)

    # Start containers
    print(f"[INFO] Starting containers from {compose_file}...")
    if not run_command(["docker-compose", "-f", compose_file, "up", "-d"]):
        print("[ERROR] Failed to start containers!")
        return False

    # Wait for services
    print()
    print("[INFO] Waiting for services to be healthy...")
    if not wait_for_services("all", retries=60, interval=5):
        print("[WARNING] Some services may not be healthy yet")

    print()
    print("=" * 50)
    print(f"  {mode} Mode Started!")
    print("=" * 50)
    print()
    print("Services running:")
    print("  - Kafka UI:    http://localhost:8081")
    print("  - PostgreSQL:  localhost:5433")
    print("  - Redis:       localhost:6379")
    if not args.lite:
        print("  - Flink UI:    http://localhost:8082")
    print()
    print("Next steps:")
    print("  python run.py producer    # Start data ingestion")
    print("  python run.py api         # Start REST/WebSocket API")
    print("  python run.py dashboard   # Start visualization")
    if args.lite:
        print("  python run.py consumer    # Start Python consumer (lite mode)")
    print()
    return True


def cmd_stop(args):
    """Stop Docker services."""
    print()
    print("[INFO] Stopping all containers...")

    # Try both compose files
    run_command(["docker-compose", "down"], check=False)
    run_command(
        ["docker-compose", "-f", "docker-compose-lite.yml", "down"], check=False
    )

    print("[OK] Containers stopped")
    return True


def cmd_producer(args):
    """Run the crypto price producer."""
    print()
    print("=" * 50)
    print("  Starting Crypto Price Producer")
    print("=" * 50)
    print()

    if not check_venv_exists():
        print("[ERROR] Virtual environment not found!")
        print("Please create it first:")
        print("  python -m venv venv")
        print("  pip install -r requirements.txt")
        return False

    if not check_docker_running():
        print("[ERROR] Docker is not running!")
        return False

    # Wait for Kafka
    print("[INFO] Checking Kafka health...")
    if not wait_for_services("kafka", retries=30, interval=3):
        print("[ERROR] Kafka is not healthy!")
        return False

    print()
    print("[INFO] Starting producer...")
    print("[INFO] Sending crypto prices to Kafka on localhost:9092")
    print()
    print("Press Ctrl+C to stop the producer")
    print()

    python = get_python_executable()
    env = {"PYTHONPATH": str(PROJECT_ROOT / "src")}

    return run_command(
        [python, str(PROJECT_ROOT / "src" / "producers" / "crypto_price_producer.py")],
        env=env,
        check=False,
    )


def cmd_api(args):
    """Run the FastAPI server."""
    print()
    print("=" * 50)
    print("  Starting Crypto Market Analyzer API")
    print("=" * 50)
    print()

    if not check_venv_exists():
        print("[ERROR] Virtual environment not found!")
        print("Please create it first:")
        print("  python -m venv venv")
        print("  pip install -r requirements.txt -r requirements-api.txt")
        return False

    # Check services health
    if check_docker_running():
        print("[INFO] Checking backend services...")
        wait_for_services("all", retries=20, interval=3)
    else:
        print("[WARNING] Docker is not running - API may have limited functionality")

    print()
    print("[INFO] Starting FastAPI server on http://localhost:8000")
    print("[INFO] API Documentation: http://localhost:8000/docs")
    print("[INFO] WebSocket Test: http://localhost:8000/ws/test")
    print()
    print("Press Ctrl+C to stop the server")
    print()

    python = get_python_executable()

    return run_command(
        [
            python,
            "-m",
            "uvicorn",
            "src.api.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--reload",
        ],
        check=False,
    )


def cmd_dashboard(args):
    """Run the Streamlit dashboard."""
    print()
    print("=" * 50)
    print("  Starting Crypto Market Dashboard")
    print("=" * 50)
    print()

    if not check_venv_exists():
        print("[ERROR] Virtual environment not found!")
        print("Please create it first:")
        print("  python -m venv venv")
        print("  pip install -r requirements.txt -r requirements-dashboard.txt")
        return False

    # Check if API is running
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:8000/health", timeout=2):
            print("[OK] API is running")
    except Exception:
        print("[WARNING] API is not running!")
        print("[INFO] Start it with: python run.py api")
        print()

    print()
    print("[INFO] Starting Streamlit dashboard on http://localhost:8501")
    print()
    print("Press Ctrl+C to stop the dashboard")
    print()

    python = get_python_executable()

    return run_command(
        [
            python,
            "-m",
            "streamlit",
            "run",
            str(PROJECT_ROOT / "src" / "dashboard" / "app.py"),
            "--server.port",
            "8501",
            "--server.headless",
            "true",
        ],
        check=False,
    )


def cmd_consumer(args):
    """Run the simple Python consumer (for lite mode)."""
    print()
    print("=" * 50)
    print("  Starting Simple Consumer (Lite Mode)")
    print("=" * 50)
    print()

    if not check_venv_exists():
        print("[ERROR] Virtual environment not found!")
        return False

    if not check_docker_running():
        print("[ERROR] Docker is not running!")
        return False

    print("[INFO] Checking Kafka health...")
    if not wait_for_services("kafka", retries=30, interval=3):
        print("[ERROR] Kafka is not healthy!")
        return False

    print()
    print("[INFO] Starting Python consumer...")
    print("[INFO] This replaces Flink processing in Lite Mode")
    print()
    print("Press Ctrl+C to stop the consumer")
    print()

    python = get_python_executable()
    env = {"PYTHONPATH": str(PROJECT_ROOT / "src")}

    return run_command(
        [python, str(PROJECT_ROOT / "src" / "consumers" / "simple_consumer.py")],
        env=env,
        check=False,
    )


def cmd_status(args):
    """Check status of all services."""
    print()
    print("=" * 50)
    print("  Service Status")
    print("=" * 50)
    print()

    if not check_docker_running():
        print("[ERROR] Docker is not running!")
        return False

    run_command(["docker-compose", "ps"], check=False)

    print()
    print("-" * 50)
    print()

    # Check each service
    services = [
        "zookeeper",
        "kafka",
        "postgres",
        "redis",
        "flink-jobmanager",
        "flink-taskmanager",
    ]

    for service in services:
        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Status}} ({{.State.Health.Status}})",
                    service,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                status = result.stdout.strip().replace(
                    "(<no value>)", "(no healthcheck)"
                )
                print(f"  {service}: {status}")
            else:
                print(f"  {service}: not running")
        except Exception:
            print(f"  {service}: unknown")

    print()
    return True


def cmd_logs(args):
    """View logs for a service."""
    service = args.service if args.service else ""

    cmd = ["docker-compose", "logs", "-f"]
    if service:
        cmd.append(service)

    return run_command(cmd, check=False)


def cmd_health(args):
    """Check health of Docker services."""
    services = args.services if args.services else ["all"]
    return wait_for_services(" ".join(services))


def main():
    parser = argparse.ArgumentParser(
        description="Cross-platform launcher for Real-Time Cryptocurrency Market Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  start       Start Docker services (--lite for low RAM systems)
  stop        Stop all Docker services
  producer    Run the crypto price producer
  api         Run the FastAPI server
  dashboard   Run the Streamlit dashboard
  consumer    Run Python consumer (for lite mode)
  status      Check status of all services
  logs        View logs (optionally specify service name)
  health      Check health of Docker services

Examples:
  python run.py start                 # Start full mode
  python run.py start --lite          # Start lite mode
  python run.py producer
  python run.py api
  python run.py dashboard
  python run.py status
  python run.py logs kafka
  python run.py health kafka postgres
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # start command
    start_parser = subparsers.add_parser("start", help="Start Docker services")
    start_parser.add_argument(
        "--lite",
        "-l",
        action="store_true",
        help="Use lite mode (for systems with <16GB RAM)",
    )
    start_parser.set_defaults(func=cmd_start)

    # stop command
    stop_parser = subparsers.add_parser("stop", help="Stop Docker services")
    stop_parser.set_defaults(func=cmd_stop)

    # producer command
    producer_parser = subparsers.add_parser(
        "producer", help="Run the crypto price producer"
    )
    producer_parser.set_defaults(func=cmd_producer)

    # api command
    api_parser = subparsers.add_parser("api", help="Run the FastAPI server")
    api_parser.set_defaults(func=cmd_api)

    # dashboard command
    dashboard_parser = subparsers.add_parser(
        "dashboard", help="Run the Streamlit dashboard"
    )
    dashboard_parser.set_defaults(func=cmd_dashboard)

    # consumer command
    consumer_parser = subparsers.add_parser(
        "consumer", help="Run Python consumer (lite mode)"
    )
    consumer_parser.set_defaults(func=cmd_consumer)

    # status command
    status_parser = subparsers.add_parser("status", help="Check status of services")
    status_parser.set_defaults(func=cmd_status)

    # logs command
    logs_parser = subparsers.add_parser("logs", help="View service logs")
    logs_parser.add_argument("service", nargs="?", help="Service name (optional)")
    logs_parser.set_defaults(func=cmd_logs)

    # health command
    health_parser = subparsers.add_parser("health", help="Check service health")
    health_parser.add_argument(
        "services", nargs="*", default=["all"], help="Services to check (default: all)"
    )
    health_parser.set_defaults(func=cmd_health)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Change to project root
    os.chdir(PROJECT_ROOT)

    # Run the command
    success = args.func(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
