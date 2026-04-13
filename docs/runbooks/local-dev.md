# Local Development Runbook

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop (for Postgres)
- Azure CLI (`az login` to acquire default credentials)
- `psql` client (optional, for DB inspection)

## 1. Start Postgres

```bash
docker-compose up -d postgres
```

This brings up a Postgres 16 container with pgvector, exposed on `localhost:5432`.
Default credentials come from `docker-compose.yml`.

## 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env             # create if missing — see variables below
alembic upgrade head
python -m scripts.seed           # optional: idempotent demo data
uvicorn app.main:app --reload --port 8000
```

### Required `.env` variables

```
DATABASE_URL=postgresql+asyncpg://rmp_dev:rmp_dev_password@localhost:5432/riskmanagerpro
APP_ENV=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173

# Azure (use `az login` creds via DefaultAzureCredential)
AZURE_OPENAI_ENDPOINT=https://<your-aoai>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
AZURE_OPENAI_API_VERSION=2024-10-21

AZURE_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
AZURE_SEARCH_INDEX_NAME=rmp-documents

AZURE_STORAGE_ACCOUNT_NAME=<your-sa-name>
AZURE_STORAGE_CONTAINER_NAME=documents

AZURE_AD_TENANT_ID=<tenant-id>
AZURE_AD_CLIENT_ID=<app-client-id>
AZURE_AD_AUTHORITY=https://login.microsoftonline.com/<tenant-id>

# RBAC rollout flag — leave false locally to avoid 403 loops during dev
RMP_ENFORCE_RBAC=false
```

Never commit `.env`. See `backend/.gitignore`.

## 3. Frontend

```bash
cd frontend
npm ci
npm run dev
```

Set `frontend/.env.local`:

```
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_AZURE_AD_CLIENT_ID=<spa-client-id>
VITE_AZURE_AD_AUTHORITY=https://login.microsoftonline.com/<tenant-id>
VITE_AZURE_AD_REDIRECT_URI=http://localhost:5173
VITE_API_SCOPE=api://<api-client-id>/access_as_user
```

## 4. Migrations

```bash
cd backend
alembic upgrade head           # apply all pending
alembic downgrade -1           # revert one
alembic revision -m "message"  # create new migration (manual schema)
alembic history                # view revision tree
```

When adding new SQLAlchemy models, import them from `app/models/__init__.py`
so autogenerate picks them up.

## 5. RBAC Rollout Notes

The `RMP_ENFORCE_RBAC` env flag gates whether missing membership roles return
403 or fall through. Keep it `false` in dev so local users without proper
memberships can still hit the API. Enable `true` in production once the
membership backfill script has run:

```bash
python -m scripts.backfill_memberships --all-orgs
```

## 6. Tests

Backend:

```bash
cd backend
# Ensure docker-compose postgres is up
pytest                        # full suite
pytest tests/api/test_rbac.py # focused
```

Frontend:

```bash
cd frontend
npm test                       # vitest once
npm run test:watch             # watch mode
npm run test:coverage          # with coverage report
```

## 7. Known Gotchas

- `DATABASE_URL` *must* be set — app refuses to boot without it.
- If you see `sslmode=require` errors, the connection string conversion in
  `app/core/config.py` handles it automatically for asyncpg.
- MSAL tokens are cached in session storage — clear via DevTools → Application
  → Storage if you see stale-token 401s.
- App Insights is a no-op locally (no `APPLICATIONINSIGHTS_CONNECTION_STRING`
  set); ignore `telemetry_configured` log absence.
- Entra ID login needs your account added as a guest to the app registration.
  Ask the Faith Group admin (Thomas Duncan) if `hello@eeko.systems` or your
  account is not yet invited.

## 8. Useful Commands

```bash
# Reset DB
docker-compose down -v && docker-compose up -d postgres && cd backend && alembic upgrade head

# Open DB shell
psql postgresql://rmp_dev:rmp_dev_password@localhost:5432/riskmanagerpro

# Inspect enum types
\dT+ risklevel

# Tail backend logs in JSON
uvicorn app.main:app --reload | jq .
```
