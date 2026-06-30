# 🛡️ Production Data Reliability Platform

> **Enterprise-grade data quality monitoring and alerting platform** — detect schema drift, freshness violations, null explosions, and volume anomalies before your users do.

[![CI](https://github.com/Indir07/Production-Data-Reliability-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Indir07/Production-Data-Reliability-Platform/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 What Is This?

This platform is a **self-hosted data observability system** — similar to [Monte Carlo](https://www.montecarlodata.com/), [Bigeye](https://www.bigeye.com/), and [Soda](https://www.soda.io/) — but built from scratch as a production-grade reference implementation.

It monitors data pipelines running on **PostgreSQL, BigQuery, Snowflake, and Delta Lake**, and alerts data engineers within seconds of a quality failure.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                    │
│   PostgreSQL │ BigQuery │ Snowflake │ Delta Lake │ Redshift │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    CHECK ENGINE (FastAPI)                    │
│   Freshness │ Schema Drift │ Volume │ Nulls │ Duplicates    │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   PostgreSQL           Redis            Prometheus
  (TimescaleDB)      (Job Queue)      (Metrics Store)
        │                                      │
        ▼                                      ▼
  Alert Router                           Grafana
  (Celery)                              Dashboards
        │
   ┌────┴────┬──────────┐
   ▼         ▼          ▼
Slack    PagerDuty   Email
```

---

## ✅ Features

| Feature | Status |
|---|---|
| 🏗️ FastAPI REST API | ✅ Sprint 0 |
| 🗄️ PostgreSQL + TimescaleDB | ✅ Sprint 0 |
| 📊 Prometheus metrics | ✅ Sprint 0 |
| 📈 Grafana dashboards | ✅ Sprint 0 |
| 🔍 Freshness checker | 🚧 Sprint 1 |
| 🔍 Schema drift detector | 🚧 Sprint 1 |
| 🔍 Null explosion checker | 🚧 Sprint 1 |
| 🔍 Volume anomaly detector | 🚧 Sprint 1 |
| 🔍 Duplicate checker | 🚧 Sprint 1 |
| 📦 Celery worker + scheduler | 🚧 Sprint 3 |
| 🚨 Slack / PagerDuty / Email alerts | 🚧 Sprint 4 |
| 🔐 JWT Auth + RBAC | 🚧 Sprint 7 |
| ☸️ Kubernetes + Helm | 🚧 Sprint 7 |
| 🌍 Terraform infra | 🚧 Sprint 7 |

---

## 🚀 Quick Start

### Prerequisites
- Docker + Docker Compose
- Python 3.12+
- Make

### 1. Clone and configure
```bash
git clone https://github.com/Indir07/Production-Data-Reliability-Platform.git
cd Production-Data-Reliability-Platform
cp .env.example .env
```

### 2. Start the stack
```bash
make up
```

### 3. Verify services
| Service | URL |
|---|---|
| API Docs (Swagger) | http://localhost:8000/docs |
| API Health | http://localhost:8000/api/v1/health |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / pdrp_admin) |
| Marquez (OpenLineage) | http://localhost:5000 |

---

## 🧱 Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API | FastAPI | Async, auto OpenAPI docs, production-proven |
| Task Queue | Celery + Redis | Battle-tested, horizontal scaling |
| Database | PostgreSQL + TimescaleDB | Time-series check history with full SQL |
| Metrics | Prometheus + Grafana | Industry standard observability |
| Lineage | OpenLineage + Marquez | Open standard, Airflow/dbt native |
| Auth | JWT + OAuth2 | Enterprise SSO ready |
| Containers | Docker + Kubernetes | From local dev to production |
| IaC | Terraform | Reproducible cloud infrastructure |
| CI/CD | GitHub Actions | Lint → Test → Build → Deploy |

---

## 📁 Project Structure

```
production-data-reliability-platform/
├── .github/workflows/     # CI/CD pipelines
├── infra/
│   ├── db/               # Database init scripts
│   ├── prometheus/       # Prometheus config
│   ├── grafana/          # Grafana provisioning
│   ├── terraform/        # Cloud infrastructure (Sprint 7)
│   └── helm/             # Kubernetes charts (Sprint 7)
├── services/
│   ├── api/              # FastAPI application
│   │   ├── app/
│   │   │   ├── checks/   # Check engine modules
│   │   │   ├── routers/  # API endpoints
│   │   │   ├── models/   # SQLAlchemy models
│   │   │   └── alerting/ # Notification channels
│   │   └── tests/
│   └── worker/           # Celery worker (Sprint 3)
├── integrations/
│   ├── airflow/          # Custom Airflow operator (Sprint 6)
│   ├── dbt/              # dbt result parser (Sprint 6)
│   └── great_expectations/ # GE importer (Sprint 6)
├── docker-compose.yml
├── Makefile
└── docs/
```

---

## 🧪 Running Tests

```bash
make test        # Run all tests
make test-cov    # Run with coverage report
make lint        # Lint with ruff
make lint-fix    # Auto-fix lint errors
```

---

## 📚 Documentation

- [Architecture & PRD](docs/ARCHITECTURE.md)
- [API Reference](http://localhost:8000/docs) *(when running locally)*
- [Runbook](docs/RUNBOOK.md) *(Sprint 8)*
- [Architecture Decision Records](docs/DECISIONS.md) *(Sprint 8)*

---

## 🗺️ Roadmap

| Sprint | Milestone | Status |
|---|---|---|
| 0 | Foundation scaffold, Docker stack, FastAPI, CI | ✅ Done |
| 1 | Core check engine (5 check types) | 🚧 Next |
| 2 | REST API + PostgreSQL + Alembic | ⬜ Planned |
| 3 | Celery workers + scheduler | ⬜ Planned |
| 4 | Alerting (Slack, PagerDuty, Email) | ⬜ Planned |
| 5 | Observability (Prometheus, Grafana, Lineage) | ⬜ Planned |
| 6 | Integrations (Airflow, dbt, GE) | ⬜ Planned |
| 7 | Auth, RBAC, K8s, Terraform | ⬜ Planned |
| 8 | Documentation, runbook, polish | ⬜ Planned |

---

## 🤝 Author

**Indir** — Data Engineer  
📍 Applying for Data Engineering roles in the Netherlands & Europe  
🔗 [GitHub](https://github.com/Indir07)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
