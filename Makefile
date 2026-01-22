# Real-Time Cryptocurrency Market Analyzer - Make Command Center
# Cross-platform commands for Docker services and application management
#
# Usage:
#   make help           - Show available commands
#   make start          - Start full mode (8GB+ RAM required)
#   make start-lite     - Start lite mode (<16GB RAM systems)
#   make producer       - Run the producer
#   make api            - Run the API
#   make dashboard      - Run the dashboard

# Variables
DC = docker-compose
DC_LITE = docker-compose -f docker-compose-lite.yml
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

.PHONY: help setup setup-api setup-dashboard start start-lite stop status health \
        logs build-flink deploy-flink stop-flink producer api dashboard consumer clean

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
	@grep -E '^(start|stop|status|health|logs)[a-zA-Z_-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Application Commands:"
	@grep -E '^(producer|api|dashboard|consumer):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Flink Commands:"
	@grep -E '^(build-flink|deploy-flink|stop-flink):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Maintenance Commands:"
	@grep -E '^clean:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ============================================
# Setup Commands
# ============================================

setup: ## Create venv and install base dependencies
	python -m venv venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

setup-api: setup ## Install API dependencies (FastAPI, uvicorn)
	$(PIP) install -r requirements-api.txt

setup-dashboard: setup ## Install dashboard dependencies (Streamlit)
	$(PIP) install -r requirements-dashboard.txt

setup-all: setup ## Install all dependencies
	$(PIP) install -r requirements-api.txt -r requirements-dashboard.txt

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
	@echo "  make dashboard   - Start visualization"

start-lite: ## Start Docker services (lite mode - for <16GB RAM systems)
	@echo "Starting Lite Mode (for systems with <16GB RAM)..."
	@echo "Note: Flink is skipped in lite mode. Use 'make consumer' for processing."
	$(DC_LITE) up -d
	@echo ""
	@echo "Waiting for services to be healthy..."
	$(PYTHON_CMD) scripts/wait_for_services.py all --retries 60 --interval 5
	@echo ""
	@echo "Lite Mode started! Next steps:"
	@echo "  make producer    - Start data ingestion"
	@echo "  make consumer    - Start Python consumer (replaces Flink)"
	@echo "  make api         - Start REST/WebSocket API"
	@echo "  make dashboard   - Start visualization"

stop: ## Stop all Docker containers
	$(DC) down
	$(DC_LITE) down 2>/dev/null || true

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

producer: ## Run the Python Data Producer
	@echo "Starting Crypto Price Producer..."
	$(PYTHON_CMD) scripts/wait_for_services.py kafka --retries 30 --interval 3
	PYTHONPATH=src $(PYTHON) src/producers/crypto_price_producer.py

api: ## Run the FastAPI Backend
	@echo "Starting FastAPI Server..."
	@echo "API Docs: http://localhost:8000/docs"
	$(PYTHON) -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

dashboard: ## Run the Streamlit Dashboard
	@echo "Starting Streamlit Dashboard..."
	@echo "Dashboard: http://localhost:8501"
	$(PYTHON) -m streamlit run src/dashboard/app.py --server.port 8501 --server.headless true

consumer: ## Run Python consumer (for lite mode, replaces Flink)
	@echo "Starting Python Consumer (Lite Mode)..."
	$(PYTHON_CMD) scripts/wait_for_services.py kafka --retries 30 --interval 3
	PYTHONPATH=src $(PYTHON) src/consumers/simple_consumer.py

# ============================================
# Flink Commands
# ============================================

build-flink: ## Compile the Flink Java Job (requires Maven + Java 11/17)
	cd src/flink_jobs && mvn clean package -DskipTests

deploy-flink: ## Build and Submit the Flink Job (Cancels old job if running)
	@echo "Copying JAR to JobManager..."
	docker cp $(JAR_PATH) $(FLINK_JM):/opt/flink/
	@echo "Checking for running jobs..."
	@JOB_ID=$$(docker exec $(FLINK_JM) flink list | grep 'RUNNING' | awk '{print $$4}'); \
	if [ ! -z "$$JOB_ID" ]; then \
		echo "Cancelling running job: $$JOB_ID"; \
		docker exec $(FLINK_JM) flink cancel $$JOB_ID; \
		sleep 5; \
	fi
	@echo "Submitting new job..."
	docker exec $(FLINK_JM) flink run -d $(DOCKER_JAR_PATH)

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
	$(DC_LITE) down -v 2>/dev/null || true
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
run-dashboard: dashboard
