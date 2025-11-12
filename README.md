# Real-Time Cryptocurrency Market Analyzer

> A streaming data project to analyze cryptocurrency markets in real-time using Apache Kafka and Apache Flink

## 🎯 Project Goals

This project demonstrates:
- Real-time data ingestion from cryptocurrency APIs
- Stream processing with Apache Flink
- Event-driven architecture with Apache Kafka
- Windowing, aggregations, and stateful processing
- End-to-end data pipeline implementation
- Professional Git workflow with feature branches

**Target**: Portfolio piece for FAANG/Big Tech internship applications

---

## 📋 Project Structure

```
Real-Time-Cryptocurrency-Market-Analyzer/
├── docker-compose.yml          # Infrastructure setup
├── configs/                    # Service configurations
│   └── init-db.sql            # PostgreSQL schema
├── src/                        # Source code (upcoming)
│   ├── producers/             # Kafka producers
│   ├── consumers/             # Kafka consumers
│   └── flink_jobs/            # Flink streaming jobs
├── .github/                    # GitHub templates
├── GIT_WORKFLOW.md            # Branching strategy
├── DATABASE_CONNECTIONS.md    # DB connection guide
├── PHASE2_DAY1-2.md          # Day 1-2 instructions
├── PHASE2_DAY3-4.md          # Day 3-4 instructions
└── README.md                   # This file
```

---

## 🚀 Quick Start

### Prerequisites
- Docker Desktop installed and running
- Git installed
- PowerShell or Git Bash

### Launch the Stack

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/Real-Time-Cryptocurrency-Market-Analyzer.git
cd Real-Time-Cryptocurrency-Market-Analyzer

# Start all services
docker-compose up -d

# Verify all containers are running
docker-compose ps

# Access UIs:
# - Kafka UI: http://localhost:8081
# - pgAdmin: http://localhost:5050
```

---

## 🚀 Phase 2: Infrastructure Setup (CURRENT)

### Week 3: Docker Environment Setup

#### **Day 1-2: Kafka Stack** ✅ **COMPLETED**

**What was built:**
- ✅ Zookeeper for Kafka metadata management
- ✅ Kafka broker with dual-listener configuration
- ✅ Kafka UI for visual cluster management
- ✅ Fixed Docker networking with internal/external listeners
- ✅ Created test-topic with 3 partitions
- ✅ Successfully produced and consumed first message

**Key learnings:**
- Docker networking with multiple listeners
- Kafka advertised listeners for container communication
- Offset-based message storage
- Partition assignment and ordering

**Access:**
- Kafka UI: http://localhost:8081
- Kafka Broker: localhost:9092 (external) / kafka:29092 (internal)

---

#### **Day 3-4: PostgreSQL & Redis** ✅ **IN PROGRESS**

**What's being added:**
- 🔄 PostgreSQL 15 for historical data storage
- 🔄 Redis 7 for in-memory caching
- 🔄 pgAdmin for database management
- 🔄 Database schema with 5 tables and 2 views
- 🔄 Health checks for all database services

**Database Schema:**
1. `cryptocurrencies` - Master table (BTC, ETH)
2. `raw_price_data` - High-frequency price updates
3. `price_aggregates_1m` - Pre-computed 1-minute OHLC
4. `price_alerts` - User-defined alerts
5. `processing_metadata` - Kafka offset tracking

**Access:**
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- pgAdmin: http://localhost:5050

**See:** `PHASE2_DAY3-4.md` for detailed setup instructions

---

#### **Day 5-7: Flink Integration** (Coming Next)

- Apache Flink JobManager and TaskManager
- Flink Web UI configuration
- Test Flink job submission
- Integration with Kafka

---

### Week 4: Basic Data Pipeline (Upcoming)

- Cryptocurrency price producer (CoinGecko API)
- Kafka consumer with filtering logic
- End-to-end: API → Kafka → Console
- Data persistence to PostgreSQL

---

## 📚 Learning Resources

### Completed
- ✅ Phase 1: Streaming Fundamentals
  - Tyler Akidau's "Streaming 101" & "Streaming 102"
  - Apache Kafka core concepts
  - Flink architecture overview

### Current Focus
- 🔄 Docker Compose orchestration
- 🔄 PostgreSQL time-series optimization
- 🔄 Redis caching patterns

### Documentation
- [Git Workflow](GIT_WORKFLOW.md) - Branching strategy
- [Database Connections](DATABASE_CONNECTIONS.md) - Connection guide
- [Docker Commands](DOCKER_COMMANDS.md) - Quick reference
- [Phase 2 Day 1-2](PHASE2_DAY1-2.md) - Kafka setup
- [Phase 2 Day 3-4](PHASE2_DAY3-4.md) - Database setup

---

## 🎓 Interview Talking Points

### Architecture Decisions

**1. Dual-Listener Kafka Configuration:**
> "I configured Kafka with dual listeners - port 29092 for internal Docker service communication and port 9092 for external client access. This is a production best practice that isolates internal traffic and provides security boundaries."

**2. Time-Series Database Design:**
> "I implemented a two-tier storage strategy: raw_price_data for high-frequency updates with 7-day retention, and price_aggregates_1m for long-term analysis. This optimizes storage costs while maintaining query performance for different use cases."

**3. Git Workflow:**
> "I follow a simplified GitHub Flow with feature branches. Each phase develops in isolated branches that merge to develop via pull requests, then weekly releases to main with semantic version tags. This mirrors industry practices for collaborative development."

**4. Infrastructure as Code:**
> "The entire stack is defined in docker-compose.yml, making it reproducible across environments. Anyone can run `docker-compose up` and have an identical setup. This is critical for team collaboration and CI/CD pipelines."

---

## 📝 Progress Tracker

- [x] **Phase 1:** Streaming Fundamentals (Weeks 1-2)
- [ ] **Phase 2:** Infrastructure Setup (Weeks 3-4) **← IN PROGRESS**
  - [x] Week 3: Docker Environment
    - [x] Day 1-2: Kafka + Zookeeper + UI
    - [x] Day 3-4: PostgreSQL + Redis *(in progress)*
    - [ ] Day 5-7: Add Flink
  - [ ] Week 4: Basic Data Pipeline
- [ ] **Phase 3:** Stream Processing Core (Weeks 5-7)
- [ ] **Phase 4:** API & Visualization (Weeks 8-9)
- [ ] **Phase 5:** Final Polish (Week 10)

---

## 🛠️ Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Message Broker | Apache Kafka | 7.5.0 | Event streaming platform |
| Coordination | Apache Zookeeper | 7.5.0 | Kafka cluster management |
| Stream Processing | Apache Flink | TBD | Real-time data processing |
| Database | PostgreSQL + TimescaleDB | latest-pg15 | Time-series data storage |
| Cache | Redis | 7-alpine | In-memory fast access |
| DB Management | pgAdmin | latest | Database GUI |
| Orchestration | Docker Compose | 3.8 | Container management |
| Monitoring | Kafka UI | latest | Visual cluster management |
| Data Source | CoinGecko API | v3 | Cryptocurrency prices |

---

## 🌐 Service Ports

| Service | Port | Access URL |
|---------|------|-----------|
| Kafka (External) | 9092 | localhost:9092 |
| Kafka (Internal) | 29092 | kafka:29092 |
| Kafka UI | 8081 | http://localhost:8081 |
| Zookeeper | 2181 | localhost:2181 |
| PostgreSQL | 5433 | localhost:5433 |
| pgAdmin | 5050 | http://localhost:5050 |
| Redis | 6379 | localhost:6379 |
| Flink Web UI | TBD | http://localhost:8082 |

---

## 🐳 Docker Commands Quick Reference

```bash
# Start all services
docker-compose up -d

# View status
docker-compose ps

# View logs
docker-compose logs <service_name>

# Stop all services
docker-compose stop

# Remove all containers
docker-compose down

# Remove containers and volumes (WARNING: deletes data)
docker-compose down -v

# Restart specific service
docker-compose restart <service_name>
```

See [DOCKER_COMMANDS.md](DOCKER_COMMANDS.md) for complete reference.

---

## 🔒 Security Notes

**Current Setup: Development Only**
- ⚠️ Default credentials are intentionally simple
- ⚠️ No authentication on Kafka
- ⚠️ Services exposed to localhost only

**For Production:**
- Use environment variables for secrets
- Enable Kafka SASL/SSL authentication
- Add PostgreSQL SSL/TLS
- Set Redis password with `requirepass`
- Implement network policies
- Use secrets management (e.g., HashiCorp Vault)

---

## 📈 Project Milestones

- **v0.1.0** - Initial setup + Phase 1 fundamentals
- **v0.2.0** - Phase 2 complete (infrastructure) *(target)*
- **v0.3.0** - Phase 3 complete (stream processing)
- **v0.4.0** - Phase 4 complete (API + visualization)
- **v1.0.0** - Production-ready portfolio project

---

## 🤝 Contributing

This is a personal portfolio project, but feedback is welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 📞 Contact

**Zaid** - Building this for FAANG internship applications

**Project Link:** [https://github.com/YOUR_USERNAME/Real-Time-Cryptocurrency-Market-Analyzer](https://github.com/YOUR_USERNAME/Real-Time-Cryptocurrency-Market-Analyzer)

---

**Built with 💪 as part of streaming data mastery journey**

*Last Updated: Phase 2, Week 3, Day 3-4*
