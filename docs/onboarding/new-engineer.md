# New Engineer Onboarding

Welcome to Risk Manager Pro. This guide gets you from zero to a running local environment and your
first merged change. Budget about half a day.

## 0. Mental model (read first)

Spend 20 minutes on [architecture/overview.md](../architecture/overview.md). The essentials:

- **Multi-tenant**: data is isolated by `organization_id`. Identity is one Entra tenant; data is many
  client orgs.
- **Backend layering is strict**: `api/ → services/ → repositories/ → models/`. Never skip a layer.
- **Chat-centric**: the main UX is an AI chat over a RAG pipeline; risk register / analytics / workflows
  are secondary.
- **Compliance is not optional**: auth, tenant scoping, and audit logging are required on every change.
  See [operations/security-compliance.md](../operations/security-compliance.md).

## 1. Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Desktop (for local Postgres + Azurite)
- Azure CLI (`az login` for `DefaultAzureCredential`)
- An Entra ID account invited to the app registration (ask the Faith Group admin if you can't sign in)

## 2. Get it running locally

Full detail is in the [Local Development Runbook](../runbooks/local-dev.md). The short version:

```bash
# 1. Infrastructure (Postgres + Azurite)
docker-compose up -d postgres

# 2. Backend
cd backend
python -m venv .venv && .venv\Scripts\activate     # PowerShell on Windows
pip install -e ".[dev]"
cp .env.example .env                                # fill in values (see runbook)
alembic upgrade head
python -m scripts.seed                              # optional demo data
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm ci
# create .env.local (see runbook), then:
npm run dev
```

Or use the Makefile shortcuts: `make install`, `make docker-up`, `make migrate`, `make dev`.

Verify:
- `http://localhost:8000/api/v1/health` → `200`
- `http://localhost:8000/docs` → interactive API docs
- `http://localhost:5173` → app loads and you can sign in

> Keep `RMP_ENFORCE_RBAC=false` (a.k.a. `ENFORCE_RBAC`) locally so a dev account without full memberships
> can still hit the API. It is mandatory `true` in production.

## 3. Where things live

| You want to… | Go to |
|--------------|-------|
| Add/change an endpoint | `backend/app/api/v1/<domain>.py` (+ schema, service, repository) |
| Change business logic | `backend/app/services/` |
| Change a DB query | `backend/app/repositories/` |
| Change the schema | add a model in `backend/app/models/`, then an Alembic migration |
| Change the AI behavior | `backend/app/services/{chat,rag,routing,prompts}.py` |
| Add a screen/feature | `frontend/src/components/<feature>/` + a hook in `frontend/src/hooks/` + an api module in `frontend/src/api/` |
| Change infra | `infra/` (Terraform) |

## 4. Make your first change

A safe starter task is to add a field to a response or a small UI tweak. The flow:

1. Branch: `feat/short-description` (conventional commits — `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`).
2. Backend change: update the **schema** (`schemas/`), the **service**/**repository** as needed, and the
   **route**. Add a test under `backend/tests/`.
3. Frontend change: update the **type** (`types/`), the **api module**, the **hook**, then the component.
4. Run the gates locally:
   ```bash
   # backend
   cd backend && make lint && make type-check && pytest
   # frontend
   cd frontend && npm run type-check && npm run lint && npm test
   ```
5. Open a PR. CI must pass and you need one approval.

## 5. Non-negotiables (the reviewer will check these)

- New endpoints are authenticated and role-gated (only health checks are public).
- Every query is tenant-scoped (`organization_id` / `tenant_id`).
- State-changing operations emit an audit entry.
- No secrets in code; types on every Python signature; no `any` in TypeScript.
- Errors return the structured envelope — never leak stack traces.
- Use `structlog`, never `print()`. No PII in logs.

Read [../../ENGINEERING_STANDARDS.md](../../ENGINEERING_STANDARDS.md) once in full — it is the contract.

## 6. Deploying

You generally won't deploy by hand — GitHub Actions does it on merge to `main`. If you need to, read the
[Deployment Runbook](../deployment/deployment-runbook.md). Deploys for this project run through **Azure
Cloud Shell**, not a local terminal.

## 7. Getting help

- Architecture questions → [architecture/overview.md](../architecture/overview.md)
- "What does this endpoint do?" → [api/api-reference.md](../api/api-reference.md) or `/docs`
- Aviation/safety terms → [reference/glossary.md](../reference/glossary.md)
- Local gotchas → [runbooks/local-dev.md](../runbooks/local-dev.md) §7
</content>
