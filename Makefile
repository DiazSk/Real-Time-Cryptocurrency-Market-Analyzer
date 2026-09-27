# Real-Time Cryptocurrency Market Analyzer - Make Command Center
# Cross-platform commands for Docker services and application management
#
# Usage:
#   make help           - Show available commands
#   make start          - Start full mode (8GB+ RAM required)
#   make producer       - Run the producer
#   make api            - Run the API

# Variables
DC = docker-compose
FLINK_JM = flink-jobmanager
FLINK_TM = flink-taskmanager
JAR_PATH = src/flink_jobs/target/crypto-analyzer-flink-1.0.0.jar
DOCKER_JAR_PATH = /opt/flink/crypto-analyzer-flink-1.0.0.jar

# Cross-platform Python detection
ifeq ($(OS),Windows_NT)
    VENV_BIN = venv/Scripts
    PYTHON = $(VENV_BIN)/python.exe
    PIP = $(VENV_BIN)/pip.exe
    RM = del /Q /S
else
    VENV_BIN = venv/bin
    PYTHON = $(VENV_BIN)/python
    PIP = $(VENV_BIN)/pip
    RM = rm -rf
endif

# Fallback if venv doesn't exist
PYTHON_CMD = $(shell if [ -f "$(PYTHON)" ]; then echo "$(PYTHON)"; else echo "python"; fi)

.PHONY: help setup setup-api setup-all start start-lite stop status health logs build-flink deploy-flink deploy-flink-fresh stop-flink topics producer consumer api test load-test chaos-test migrate backfill dbt dbt-docs airflow-setup airflow analysis clean

help: ## Show this help message
	@echo ""
	@echo "Real-Time Cryptocurrency Market Analyzer"
	@echo "========================================="
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Setup Commands:"
	@grep -E '^setup[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Docker Commands:"
	@grep -E '^(start|start-lite|stop|status|health|logs)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Application Commands:"
	@grep -E '^(topics|producer|consumer|api|test):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Flink Commands:"
	@grep -E '^(build-flink|deploy-flink|deploy-flink-fresh|stop-flink):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Maintenance Commands:"
	@grep -E '^clean:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ============================================
# Setup Commands
# ============================================

setup: ## Create venv and install base dependencies
	python3.12 -m venv venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

setup-api: setup ## Install API dependencies (FastAPI, uvicorn)
	$(PIP) install -r requirements-api.txt

setup-all: setup ## Install all dependencies
	$(PIP) install -r requirements-api.txt

# ============================================
# Docker Commands
# ============================================

start: ## Start Docker services (full mode - 8GB+ RAM required)
	@echo "Starting Full Mode (requires 8GB+ RAM)..."
	$(DC) up -d
	@echo ""
	@echo "Waiting for services to be healthy..."
	$(PYTHON_CMD) scripts/wait_for_services.py all --retries 60 --interval 5
	@echo ""
	@echo "Services started! Next steps:"
	@echo "  make producer    - Start data ingestion"
	@echo "  make api         - Start REST/WebSocket API"

start-lite: ## Start lite mode (no Flink — Kafka/Postgres/Redis/frontend only, 8GB RAM not required)
	@echo "Starting Lite Mode (no Flink)..."
	$(DC) -f docker-compose-lite.yml up -d
	@echo ""
	@echo "Waiting for services to be healthy..."
	$(PYTHON_CMD) scripts/wait_for_services.py all --retries 60 --interval 5
	@echo ""
	@echo "Services started! Next steps:"
	@echo "  make producer    - Start data ingestion"
	@echo "  make consumer    - Start the lite-mode OHLCV consumer (replaces Flink)"
	@echo "  make api         - Start REST/WebSocket API"

stop: ## Stop all Docker containers
	$(DC) down

status: ## Show status of all services
	@echo "Docker Compose Status:"
	@echo "======================"
	$(DC) ps
	@echo ""
	@echo "Container Health:"
	@echo "================="
	@docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || echo "Docker not running"

health: ## Check health of all services
	$(PYTHON_CMD) scripts/wait_for_services.py all --retries 10 --interval 2

logs: ## View Flink TaskManager logs
	docker logs -f $(FLINK_TM)

logs-all: ## View all container logs
	$(DC) logs -f

logs-kafka: ## View Kafka logs
	docker logs -f kafka

# ============================================
# Application Commands
# ============================================

topics: ## Create Kafka topics (idempotent)
	docker exec kafka kafka-topics --bootstrap-server localhost:9092 \
		--create --if-not-exists --topic crypto-trades --partitions 4 --replication-factor 1

producer: topics ## Run the Coinbase trade producer
	@echo "Starting Coinbase trade producer..."
	PYTHONPATH=. $(PYTHON) -m src.producers.coinbase_trades_producer

consumer: topics ## Run the lite-mode OHLCV consumer (no-Flink replacement)
	@echo "Starting lite-mode consumer..."
	PYTHONPATH=. $(PYTHON) -m src.consumers.simple_consumer

api: ## Run the FastAPI Backend
	@echo "Starting FastAPI Server..."
	@echo "API Docs: http://localhost:8000/docs"
	$(PYTHON) -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Run Python and Flink unit tests
	PYTHONPATH=. $(PYTHON) -m pytest -q
	cd src/flink_jobs && mvn -q test

migrate: ## Apply configs/migrations/*.sql to the running postgres container (idempotent)
	docker exec -i postgres sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -v ON_ERROR_STOP=1 -q' < configs/migrations/001_analytics.sql

backfill: ## Load 90 days of Coinbase 1-minute candles (then incremental) and repair trade gaps
	$(PYTHON_CMD) -m src.backfill all

dbt: ## Build and test every dbt model (analytics/), reading DB settings from .env
	set -a; . ./.env; set +a; cd analytics && ../$(VENV_BIN)/dbt deps --quiet && ../$(VENV_BIN)/dbt build

dbt-docs: ## Generate and serve the dbt docs + lineage graph on :8088
	set -a; . ./.env; set +a; cd analytics && ../$(VENV_BIN)/dbt docs generate && ../$(VENV_BIN)/dbt docs serve --port 8088

analysis: dbt ## Rebuild the marts, then re-execute analysis/market_analysis.ipynb in place (charts + findings)
	$(VENV_BIN)/jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=900 analysis/market_analysis.ipynb

AIRFLOW_VERSION = 3.3.2
AIRFLOW_CONSTRAINTS = https://raw.githubusercontent.com/apache/airflow/constraints-$(AIRFLOW_VERSION)/constraints-3.12.txt

airflow-setup: ## Create .venv-airflow with Airflow + Cosmos (kept apart: Airflow pins many shared deps)
	python3.12 -m venv .venv-airflow
	.venv-airflow/bin/pip install --quiet "apache-airflow==$(AIRFLOW_VERSION)" "astronomer-cosmos==1.15.1" --constraint $(AIRFLOW_CONSTRAINTS)

airflow: ## Run Airflow standalone (UI :8080); login password is in airflow/simple_auth_manager_passwords.json.generated
	set -a; . ./.env; set +a; export AIRFLOW_HOME=$(CURDIR)/airflow AIRFLOW__CORE__LOAD_EXAMPLES=False; .venv-airflow/bin/airflow standalone

load-test: ## Benchmark REST latency, WebSocket fan-out and freshness (full stack up; nothing on :8000)
	$(PYTHON_CMD) -m benchmarks.load_test

chaos-test: ## Inject 5 failures and measure recovery, lost trades and candle consistency (full stack up)
	$(PYTHON_CMD) -m benchmarks.chaos_test

# ============================================
# Flink Commands
# ============================================

build-flink: ## Compile the Flink Java Job (requires Maven + Java 11/17)
	cd src/flink_jobs && mvn clean package -DskipTests

deploy-flink: ## Build and Submit the Flink Job (stop-with-savepoint + resume if one is running)
	@echo "Copying JAR to JobManager..."
	docker cp $(JAR_PATH) $(FLINK_JM):/opt/flink/
	FLINK_JM=$(FLINK_JM) DOCKER_JAR_PATH=$(DOCKER_JAR_PATH) bash scripts/deploy_flink.sh

deploy-flink-fresh: ## Build and Submit the Flink Job (stateless cancel + run; state is discarded)
	@echo "Copying JAR to JobManager..."
	docker cp $(JAR_PATH) $(FLINK_JM):/opt/flink/
	FLINK_JM=$(FLINK_JM) DOCKER_JAR_PATH=$(DOCKER_JAR_PATH) bash scripts/deploy_flink.sh --fresh

stop-flink: ## Cancel any running Flink jobs
	@JOB_ID=$$(docker exec $(FLINK_JM) flink list | grep 'RUNNING' | awk '{print $$4}'); \
	if [ ! -z "$$JOB_ID" ]; then \
		echo "Cancelling job: $$JOB_ID"; \
		docker exec $(FLINK_JM) flink cancel $$JOB_ID; \
	else \
		echo "No running jobs found."; \
	fi

# ============================================
# Maintenance Commands
# ============================================

clean: ## Remove containers, volumes, and build artifacts
	$(DC) down -v
	$(RM) src/flink_jobs/target 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# ============================================
# Aliases for convenience
# ============================================
up: start
down: stop
ps: status
run-producer: producer
run-api: api
