# Deployment Runbook

This runbook covers how Risk Manager Pro is built, validated, and deployed to Azure. The
**canonical CI/CD system is Azure DevOps Pipelines** (`azure-pipelines.yml`), running in Faith Group's
Azure DevOps organization.

For the underlying Azure resources, see [infrastructure.md](infrastructure.md).

## 1. Pipeline overview

```
PR to main        ──▶ Backend CI + Frontend CI (lint, type-check, test, build)
push to main      ──▶ Backend CI + Frontend CI ──▶ Deploy*  (*only when deployEnabled = true)
                                                       │
                                                       ├─▶ Deploy Backend (Container App image + env + migrations)
                                                       └─▶ Deploy Frontend (Static Web App)
```

CI runs automatically on every PR and on pushes to `main`. The **Deploy stage is gated** behind the
`deployEnabled` pipeline variable (default `false`) so simply enabling the pipeline never auto-deploys to
production — the team flips it to `true` when ready to release from DevOps. The Infrastructure
(Terraform) stage is disabled by default because the platform targets an existing resource group; enable
it only to manage infra from the pipeline.

## 2. One-time Azure DevOps setup

These are portal/account actions (not YAML) that the team performs once in their DevOps project:

1. **Create the pipeline** — Pipelines → New pipeline → point at `azure-pipelines.yml` in this repo.
2. **Parallelism** — request the free Microsoft-hosted parallel-jobs grant (Project settings → Parallel
   jobs) or attach a self-hosted agent pool. Until granted, runs queue.
3. **Service connection** `azure-rmp-connection` — an Azure Resource Manager connection using
   **Workload Identity Federation** (no client secret). Project settings → Service connections.
4. **Variable group** `RMP variable group` — resource names + non-secret config:
   `AZURE_AD_TENANT_ID`, `AZURE_AD_CLIENT_ID`, `AZURE_OPENAI_ENDPOINT`, `AZURE_SEARCH_ENDPOINT`,
   `AZURE_SEARCH_INDEX_NAME`, `AZURE_STORAGE_ACCOUNT_NAME`, `CORS_ORIGINS`, `API_BASE_URL`,
   `FRONTEND_URL`, `DATABASE_URL`, `SWA_DEPLOYMENT_TOKEN`. Store `DATABASE_URL` /
   `db-admin-password` in **Key Vault**; the pipeline reads `db-admin-password` per-run via the
   `AzureKeyVault@2` task.
5. **(Recommended) Release gate** — create a DevOps **Environment** with required-approver checks and
   switch the Deploy jobs to deployment jobs targeting it, so production releases require human approval.

## 3. CI stages (`azure-pipelines.yml`)

| Stage / job | What it does |
|-------------|--------------|
| **Backend → Lint & Type Check** | `ruff check`, `ruff format --check`, `mypy app/` |
| **Backend → Unit Tests** | `pytest` with coverage against a Postgres-16 service container; publishes test + coverage results |
| **Backend → Docker Build & Push** | On `main`: build the API image and push to ACR (`:BuildId` + `:latest`) |
| **Frontend → Lint & Type Check** | `npm run lint`, `npm run type-check` |
| **Frontend → Build** | `npm run build` with `VITE_*` injected from the variable group; publishes the `dist/` artifact |

Run the same gates locally before pushing:

```bash
cd backend && make lint && make type-check && pytest
cd frontend && npm run type-check && npm run lint && npm test
```

## 4. Deploy stage

Runs only on `main` **and** when `deployEnabled = true`:

- **Deploy Backend (Container App)** — ensures the Container App identity's RBAC roles (OpenAI, Search,
  Storage), sets the `database-url` secret, updates the Container App to the new image with its env vars,
  and runs `alembic upgrade head`.
- **Deploy Frontend (Static Web App)** — downloads the build artifact and deploys it via the SWA CLI.

## 5. Containers

- **Backend** (`backend/Dockerfile`): multi-stage on digest-pinned `python:3.12-slim`; runs as non-root
  `appuser`; entrypoint `start.sh` runs `alembic upgrade head` then Uvicorn on port 8000;
  `HEALTHCHECK` hits `/api/v1/health`.
- **Frontend** (`frontend/Dockerfile`): build stage (`node:20-alpine`, `npm ci && npm run build`) →
  runtime `nginx:alpine` as non-root on port 8080 with SPA fallback to `index.html`. (Static Web Apps is
  the production host; the container image is available for container-based hosting.)

## 6. First-time provisioning with azd

`azure.yaml` wires the **Azure Developer CLI (azd)** to Terraform and the two services (`api` →
Container App, `web` → Static Web App). Provisioning hooks:

- **preprovision** (`scripts/preprovision.*`) — generates a strong 32-char DB admin password if not set.
- **postprovision** (`scripts/postprovision.*`) — creates/configures the Entra ID app registration, the
  `access_as_user` OAuth scope and service principal, and stores client/tenant IDs in the azd
  environment; prompts for admin consent.

```bash
azd auth login
azd env new rmp-prod
azd up                      # provision infra + deploy both services
```

> **Deployment policy for this project:** routine deploys go through **Azure Cloud Shell**, not a local
> Windows terminal. Run `az`/`azd`/Terraform commands from Cloud Shell (or let the DevOps pipeline
> perform the deploy). Always check existing Azure resources before creating new ones.

## 7. Database migrations on deploy

The backend container runs `alembic upgrade head` on startup (`start.sh`), and the Deploy stage also runs
it explicitly. A new revision therefore applies pending migrations as it boots. Author migrations so they
are safe against the live schema (additive first; avoid destructive changes in the same release as the
code that depends on the old shape).

## 8. Rollback

- **Backend:** Container App keeps prior revisions. To roll back, shift 100% of ingress traffic back to
  the previous revision and deactivate the bad one (Azure portal or `az containerapp revision`).
- **Frontend:** redeploy the previous build artifact / commit to Static Web Apps.
- **Infrastructure:** revert the Terraform change and re-apply. Note the audit-log WORM lock is
  irreversible once enabled.

## 9. Smoke checks after deploy

1. `GET {API_BASE_URL}/health` → `200`, expected version.
2. `GET {API_BASE_URL}/health/ready` → `healthy` (DB, Search, OpenAI, Storage all green).
3. Load the frontend URL, sign in with Entra ID, confirm the chat page renders and a message round-trips
   with citations.
4. Confirm an audit entry was written for the test action (admin → Audit log).

See [operations-runbook.md](../operations/operations-runbook.md) for monitoring and incident response.
</content>
