# Trend⚡ AI – Growth Intelligence Platform

Trend⚡ ingests viral conversations from X and Reddit, generates on-brand replies and daily ideas, and alerts you the moment your niche starts heating up. The project ships with a FastAPI backend, a React/Vite dashboard, background schedulers, Telegram notifications, and optional real‑time streaming.

---

## Table of Contents
1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
   - [Local (Python + Node)](#local-python--node)
   - [Docker Compose](#docker-compose)
   - [Production Notes](#production-notes)
4. [Configuration & Feature Flags](#configuration--feature-flags)
5. [Running & Monitoring](#running--monitoring)
6. [Testing & CI](#testing--ci)
7. [Documentation & Runbooks](#documentation--runbooks)

---

## Architecture
- **Backend** – FastAPI (`trend_spark_ai`) with SQLAlchemy, APScheduler, Prometheus metrics, and Telegram notifications.
- **Ingestion** – Polling search for X/Reddit, optional filtered X stream, ranking pipeline, reply generator (OpenAI), daily idea generator.
- **Frontend** – React + Vite + React Query; dashboards, automation controls, analytics, and conversation views.
- **Background worker** – APScheduler jobs (ingest, ranking, daily ideas, reply generation, archive cleanup placeholder).
- **Storage** – SQLite by default; Postgres via Docker Compose or production deployment.
- **Telemetry** – Prometheus + Grafana, structured JSON logging, Telegram alerts for API/job failures.

---

## Prerequisites
| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12 (recommended) | Compatible with 3.10+ |
| Node.js | 20.x LTS | Needed for the Vite frontend |
| npm | 10.x | ships with Node 20 |
| Docker + Compose | optional | Required for `docker compose up` |
| Make (optional) | for custom scripts if you add them |

---

## Environment Setup

### Local (Python + Node)
```bash
# Clone + enter repo
git clone <repo-url>
cd trend-spark-ai

# Python env
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Copy and configure environment
cp .env.example .env            # set API tokens, DB URL, feature flags

# Initialize DB
python -c "from trend_spark_ai.db import Base, engine; Base.metadata.create_all(bind=engine)"

# Run backend API (http://127.0.0.1:8000)
uvicorn trend_spark_ai.api:app --reload

# In a second terminal: start worker scheduler (optional if API not running with worker)
uvicorn trend_spark_ai.worker_app:app --host 0.0.0.0 --port 9000 --reload

# Frontend
cd frontend
npm install
cp .env.example .env            # set VITE_API_BASE_URL, feature flags
npm run dev                     # http://localhost:5173
```

### Docker Compose
```bash
cp .env.example .env          # include Postgres URL
cp frontend/.env.example frontend/.env
docker compose up -d --build
```
Services:
- Backend API – http://localhost:8000
- Frontend – http://localhost:4173
- Worker – http://localhost:9000
- Postgres – internal service `db:5432`
- Prometheus – http://localhost:9090
- Grafana – http://localhost:3000 (admin/admin)

### Production Notes
- Use managed Postgres (RDS, Cloud SQL). Set `DATABASE_URL`.
- Configure secrets via Vault/AWS SSM/Azure Key Vault.
- Run backend + worker as separate processes or containers (horizontal scaling).
- Enable HTTPS via reverse proxy (Nginx/Traefik) or managed ingress.
- Configure Prometheus/Grafana stack with persistent volumes or external monitoring.
- Harden Telegram/X/OpenAI credentials via secret stores; rotate regularly.

---

## Configuration & Feature Flags
Core `.env` variables (see `.env.example`):
- **OPENAI_API_KEY** – required for idea/reply generation.
- **X_BEARER_TOKEN** – enables X search. Needed for metric refresh.
- **X_STREAM_ENABLED** – `true` enables filtered stream ingestion (requires Elevate access).
- **X_STREAM_RULES** – semicolon-separated custom stream rules (defaults to KEYWORDS).
- **X_INGEST_ENABLED / REDDIT_INGEST_ENABLED** – toggle source ingestion for experiments.
- **ALERT_RECENCY_MINUTES** – filter stale posts from alerts (default 30 min).
- **FEATURE FLAGS (frontend)** – set in `frontend/.env`:  
  - `VITE_ENABLE_NEW_CHARTS=true` – reveal experimental analytics panels.  
  - `VITE_ENABLE_EXPERIMENTAL_SIDEBAR=true` – toggle new navigation layout.

Additional backend flags (optional, defaults false):
- `ENABLE_ARCHIVE_JOB=true` (placeholder — implement job to archive old posts/performance metrics).
- `ENABLE_REALTIME_ALERTS=true` (alias for telegram notifications; disable for dry run environments).

Feature-flag usage documented in [docs/configuration.md](docs/configuration.md).

---

## Growth Profiles & Scheduler Jobs

Ingestion now supports **multiple growth profiles** (keywords + watchlist bundles). Each scheduler config targets one profile so you can run concurrent jobs for different niches.

1. **Migrate the database** using [docs/migrations/2025-11-09_growth_profiles.md](docs/migrations/2025-11-09_growth_profiles.md) (adds growth profile metadata + links scheduler configs to a profile).
2. **Create/manage profiles** via the dashboard (Automation → Targeting tab) or call the admin API (`/growth/profiles` CRUD endpoints).
3. **Assign profiles to jobs**:
   - UI: Scheduler form now includes a “Growth profile” select.
   - CLI: `python -m trend_spark_ai.cli scheduler-add ingest_rank "*/10 * * * *" --growth-profile-id 2`.
4. **Worker behavior**: each job run injects the configured `growth_profile_id`; `job_ingest_and_rank` will ingest using that profile’s keywords/watchlist while other jobs (reply generation, daily ideas) simply receive the ID for logging/auditing.

If no profiles exist, the app seeds a “Default profile” from `.env` fallbacks. Archiving the default is blocked; set another profile as default first.

---

## Running & Monitoring
| Item | Command/Path |
|------|--------------|
| Health checks | `GET /live`, `GET /health` |
| Metrics | `GET /metrics` (backend + worker) |
| Scheduler state | `/scheduler/jobs`, `/scheduler/run`, `/scheduler/toggle` |
| Telegram alerts | Ensure `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` set. Alerts sent for trending posts, API error spikes, job failure streaks. |
| Prometheus data source | Grafana → Data sources → Prometheus at `http://prometheus:9090` |

Operational runbooks live in [docs/runbooks.md](docs/runbooks.md):
- Ingestion failure recovery
- Telegram alert troubleshooting
- Database retention/archive procedure
- Prometheus/Grafana access and dashboard creation

---

## Testing & CI

### Backend
```bash
pytest                   # unit tests (ranking, ingestion, generator stub)
black trend_spark_ai tests --check
flake8 trend_spark_ai tests
mypy trend_spark_ai
bandit -q -r trend_spark_ai
```

### Frontend
```bash
cd frontend
npm run lint             # ESLint (flat config)
npm run type-check       # TypeScript
npm run test:ci          # Vitest + Testing Library + coverage
npm run build
```

### GitHub Actions
Workflow: `.github/workflows/ci.yml`
- Backend job: setup-python → pip install `requirements-dev.txt` → black/flake8/mypy/bandit/pytest.
- Frontend job: setup-node → npm ci → lint → type-check → `vitest run --coverage` → build → `npm audit --audit-level=high`.
- Artifacts: coverage (frontend) stored in `frontend/coverage`. Extend as needed.

---

## Documentation & Runbooks
- [docs/onboarding.md](docs/onboarding.md) – step-by-step guide for new contributors (access requirements, env setup, test checklist, PR workflow).
- [docs/configuration.md](docs/configuration.md) – environment variables, feature flags, secrets management, retention policy.
- [docs/runbooks.md](docs/runbooks.md) – operational procedures (alerts, ingestion, scheduler, database archiving, Prometheus/Grafana dashboards).
- [docs/releases.md](docs/releases.md) *(optional slot, create as needed)* – release checklist, tagging, change-log.

Contributions should update relevant docs when introducing new features/flags/jobs. Continuous alignment of README + docs keeps onboarding fast and ops predictable.
>>>>>>> 143e202 (Initial commit: Trend⚡ backend, frontend, and infra)
