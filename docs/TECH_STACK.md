# Technology Stack — Free & Open Source Only
# Production Data Reliability Platform
# Budget: $0 | Runs entirely on Docker Compose locally

---

## Constraint

This project runs **100% locally** using Docker Compose and open-source software.
Zero cloud spend. Zero paid APIs. Every tool below is free forever.

---

## Full Stack Audit

### ✅ Already Free (Confirmed)

| Component | Tool | License | Why |
|---|---|---|---|
| API Framework | FastAPI | MIT | |
| Task Queue | Celery | BSD | |
| Message Broker | Redis 7 | BSD | |
| Database | PostgreSQL 16 | PostgreSQL License | |
| Time-Series | TimescaleDB (Community) | Timescale License | Free for self-hosted |
| Metrics | Prometheus | Apache 2.0 | |
| Dashboards | Grafana OSS | AGPL 3.0 | Free self-hosted edition |
| Lineage | Marquez (OpenLineage) | Apache 2.0 | |
| Containers | Docker + Docker Compose | Apache 2.0 | |
| CI/CD | GitHub Actions | Free for public repos | |
| Linting | ruff | MIT | |
| Testing | pytest | MIT | |
| Logging | structlog | MIT | |

---

### 🔄 Paid → Free Replacements

#### 1. Kubernetes (EKS / GKE / AKS) → **k3s or Docker Compose**
> Industry standard for prod orchestration. EKS costs ~$70/mo minimum.

**Free alternative: k3s (Rancher)**
```bash
# Install k3s locally — single binary, < 512MB RAM
curl -sfL https://get.k3s.io | sh -
```
- Full Kubernetes API compatible
- Runs on your laptop
- Same Helm charts work unchanged
- For this project: we use **Docker Compose** for local dev and document k3s for "production simulation"

#### 2. Managed RDS (PostgreSQL) → **PostgreSQL in Docker**
> AWS RDS PostgreSQL costs ~$25/mo minimum.

**Already using**: `timescale/timescaledb:latest-pg16` in Docker Compose. ✅

#### 3. ElastiCache (Redis) → **Redis in Docker**
> AWS ElastiCache costs ~$20/mo minimum.

**Already using**: `redis:7-alpine` in Docker Compose. ✅

#### 4. PagerDuty → **Alertmanager (Prometheus ecosystem)**
> PagerDuty free tier is limited to 5 users with feature restrictions.

**Free alternative: Prometheus Alertmanager**
```yaml
# alertmanager.yml
route:
  receiver: slack-notifications
receivers:
  - name: slack-notifications
    slack_configs:
      - api_url: $SLACK_WEBHOOK_URL
        channel: '#data-alerts'
```
- Handles deduplication, silencing, grouping
- Integrates natively with Prometheus
- We add this to Docker Compose in Sprint 5

#### 5. Databricks (Paid) → **Apache Spark + Delta Lake (local)**
> Databricks paid edition costs thousands/mo.

**Free alternative: Apache Spark OSS + Delta Lake OSS**
- Same APIs, runs locally in Docker
- Not needed for this project (we monitor PostgreSQL pipelines)

#### 6. Snowflake → **DuckDB (analytical queries)**
> Snowflake costs per compute second.

**Free alternative: DuckDB**
- In-process analytical database, zero infrastructure
- Can query Parquet, CSV, PostgreSQL
- We use it for baseline computation in Sprint 5

#### 7. Confluence / Notion (docs) → **GitHub Wiki + Markdown**
> Free via GitHub. Already using this.

#### 8. Datadog (APM) → **Prometheus + Grafana + Jaeger**
> Datadog costs ~$15/host/month.

**Free alternative (already in stack)**:
- Prometheus: metrics
- Grafana OSS: dashboards
- Jaeger: distributed tracing (add in Sprint 5)

#### 9. Auth0 / Okta → **Keycloak**
> Auth0 free tier limited to 7,500 MAU.

**Free alternative: Keycloak**
```yaml
# docker-compose.yml addition (Sprint 7)
keycloak:
  image: quay.io/keycloak/keycloak:24.0
  environment:
    KEYCLOAK_ADMIN: admin
    KEYCLOAK_ADMIN_PASSWORD: admin
  command: start-dev
  ports:
    - "8080:8080"
```
- Full OAuth2/OIDC server
- Self-hosted, unlimited users
- Same JWT tokens, same RBAC model

#### 10. dbt Cloud → **dbt Core (CLI)**
> dbt Cloud costs $100+/seat/month.

**Free alternative: dbt Core**
```bash
pip install dbt-postgres
dbt run --profiles-dir .
```
- Identical SQL transformations
- Runs locally or in CI
- We wire this in Sprint 6

#### 11. Great Expectations Cloud → **Great Expectations OSS**
> GE Cloud has paid tiers.

**Free alternative: great_expectations Python library**
```bash
pip install great_expectations
```
- Full suite runner, all check types
- We import GE suites as PDRP check configs in Sprint 6

---

## Updated Docker Compose Services (All Free)

```
pdrp-api          FastAPI              :8000   MIT
pdrp-worker       Celery               -       BSD
pdrp-db           PostgreSQL+Timescale :5432   OSS
pdrp-redis        Redis 7              :6379   BSD
pdrp-prometheus   Prometheus           :9090   Apache 2.0
pdrp-alertmanager Alertmanager         :9093   Apache 2.0  (Sprint 5)
pdrp-grafana      Grafana OSS          :3000   AGPL
pdrp-marquez      Marquez/OpenLineage  :5000   Apache 2.0
pdrp-jaeger       Jaeger tracing       :16686  Apache 2.0  (Sprint 5)
pdrp-keycloak     Keycloak             :8080   Apache 2.0  (Sprint 7)
pdrp-mailhog      MailHog (SMTP dev)   :8025   MIT         (Sprint 4)
```

**Total cloud cost: $0/month**
**Total RAM needed: ~4GB** (comfortable on any dev laptop)

---

## Resume Framing

When a recruiter asks "have you used Kubernetes?":
> "Yes — I deployed this platform using Helm charts on k3s locally,
> which is production-identical to EKS. The same charts would deploy
> to any managed Kubernetes cluster with a single values override."

When asked "have you used cloud databases?":
> "I designed the schema for PostgreSQL + TimescaleDB and ran it locally
> in Docker. In production the same schema deploys to RDS or Cloud SQL —
> the connection string is the only change."

You demonstrate the *skill*, not the *credit card*.
