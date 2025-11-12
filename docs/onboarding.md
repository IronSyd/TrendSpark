# Contributor Onboarding Guide

Welcome to Trend⚡! This guide walks new contributors through access requests, local setup, coding standards, and validation before opening a pull request.

---

## 1. Accounts & Access
| System | Purpose | Access Path |
|--------|---------|-------------|
| GitHub Repository | Source control | Request write access from project owner |
| OpenAI account | Reply/idea generation | Use existing team key or create a personal API key for local testing |
| X (Twitter) API | Ingestion + metrics | Requires Elevated access (project bearer token) |
| Reddit API | Trend ingestion | Create an app at <https://www.reddit.com/prefs/apps> |
| Telegram Bot | Alerts | Ask ops for bot token + target chat ID (public channel or group) |
| Grafana | Observability | Access link: `http://localhost:3000` (default admin/admin) |

**Security:** never commit secrets. Use `.env` for local only; staging/production use secret stores (Vault/SSM/etc.).

---

## 2. Local Environment Setup
1. **Clone + virtualenv**
   ```bash
   git clone <repo>
   cd trend-spark-ai
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
2. **Configure environment**
   ```bash
   cp .env.example .env
   # Populate OPENAI_API_KEY, X_BEARER_TOKEN, REDDIT_*, TELEGRAM_*, DATABASE_URL, feature flags
   ```
3. **Database bootstrap**
   ```bash
   python - <<'PY'
   from trend_spark_ai.db import Base, engine
   Base.metadata.create_all(bind=engine)
   PY
   ```
4. **Run services**
   ```bash
   uvicorn trend_spark_ai.api:app --reload     # backend
   uvicorn trend_spark_ai.worker_app:app --port 9000 --reload   # scheduler/worker
   ```
5. **Frontend**
   ```bash
   cd frontend
   npm install
   cp .env.example .env
   npm run dev
   ```
6. **Smoke tests**
   - `GET http://127.0.0.1:8000/health`
   - React app: http://localhost:5173
   - Prometheus: http://localhost:9090 (Docker stack)

---

## 3. Coding Standards & Tooling
| Area | Command |
|------|---------|
| Backend formatting | `black trend_spark_ai tests --check` |
| Backend lint | `flake8 trend_spark_ai tests` |
| Backend typing | `mypy trend_spark_ai` |
| Backend security | `bandit -q -r trend_spark_ai` |
| Backend tests | `pytest` |
| Frontend lint | `npm run lint` |
| Frontend type-check | `npm run type-check` |
| Frontend tests | `npm run test:ci` |
| Frontend build | `npm run build` |

> Tip: run `pip install -r requirements-dev.txt` and `npm ci` to ensure the same versions as CI.

---

## 4. Git Workflow
1. Create feature branch: `git checkout -b feat/my-change`.
2. Commit with descriptive messages (`feat`, `fix`, `docs`, etc.).
3. Before push: run full test suite (backend + frontend).
4. Push and open PR:
   - Include summary, testing evidence, screenshots if UI.
   - Update docs/README when changing config, env vars, or workflows.
5. PR approval requires:
   - CI passing (lint, tests, security).
   - At least one reviewer approval.
   - Resolve merge conflicts; re-run `docker compose build` if infrastructure is touched.

---

## 5. Helpful Commands
```bash
# Run all backend checks
black trend_spark_ai tests && \
flake8 trend_spark_ai tests && \
mypy trend_spark_ai && \
pytest

# Backend + worker with watch mode
uvicorn trend_spark_ai.api:app --reload
uvicorn trend_spark_ai.worker_app:app --port 9000 --reload

# Frontend test watch
cd frontend && npm run test

# Docker full stack
docker compose up -d --build
```

---

## 6. Support Channels
- **Slack/Discord** – #trend-ai-dev (feature questions, pairing)
- **Ops Hotline** – `@on-call-trendai` (production issues)
- **Docs** – [`docs/runbooks.md`](runbooks.md) for incident procedures, [`docs/configuration.md`](configuration.md) for flags/secrets.

Set up your environment, run the smoke checks, and you’re ready to ship! Welcome aboard. 🚀
