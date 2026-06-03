# Deployment Runbook

This runbook covers how Risk Manager Pro is built, validated, and deployed to Azure. The
**canonical CI/CD system is GitHub Actions**. The Azure DevOps pipeline (`azure-pipelines.yml`) is
present but **disabled** (triggers set to `none`); treat GitHub Actions as the source of truth.

For the underlying Azure resources, see [infrastructure.md](infrastructure.md).

## 1. Pipelines overview

```
PR / push to main ──▶ ci.yml (lint, type-check, test, build, security scan, IaC validate)
                          │  on success
                          ▼
                     deploy.yml ──▶ deploy-infra (Terraform apply)
                          │            │
                          │            ├─▶ build-and-deploy-backend (image build/scan/push, rollout, health-gated)
                          │            └─▶ deploy-frontend (build + deploy to Static Web Apps)
                     [production environment: requires approval]
```

## 2. CI — `.github/workflows/ci.yml`

Runs on every PR and push to `main`. Jobs (parallel where possible):

| Job | What it does |
|-----|--------------|
| `backend-lint` | `ruff check`, `ruff format --check`, `mypy app/` |
| `backend-test` | `pytest` with coverage against a Postgres-16 + pgvector service container |
| `security-scan` | `pip-audit` (backend deps), `npm audit` (frontend, `--audit-level=high`) |
| `sast` | `bandit` over `backend/app/` (config from `pyproject.toml`) |
| `frontend-lint` | `npm run type-check`, `npm run lint` |
| `frontend-test` | `npm test` (Vitest) |
| `frontend-build` | `npm run build` |
| `terraform-validate` | `terraform validate`, `fmt -check`, and `tfsec` (fails on CRITICAL) |

All jobs must pass before `deploy.yml` is eligible to run.

## 3. Deploy — `.github/workflows/deploy.yml`

Triggers on a **successful CI run on `main`**, or manually via `workflow_dispatch`. Azure auth uses
**OIDC federation** (`id-token: write`) — no stored client secret.

| Job | What it does |
|-----|--------------|
| `check-ci` | Gate: only proceed if CI passed **and** the run originated from this repo (blocks forked-PR runs from using production credentials). |
| `deploy-infra` | `terraform init` (remote state) → `plan -var-file=environments/<TF_ENV>.tfvars` → `apply`. Tenant/client IDs and the DB password are injected from secrets. |
| `build-and-deploy-backend` | Build the backend image, **Trivy** scan (fail on CRITICAL/HIGH), push to ACR tagged with the commit SHA, update the Container App with a new revision suffix, then **health-gate**: poll `/health` for ~90s and **roll back to the previous revision on failure**. |
| `deploy-frontend` | `npm ci && npm run build` (with `VITE_*` injected from repo variables), then deploy `dist/` to Azure Static Web Apps. |

The `production` GitHub environment requires approval, so infra/app changes pause for a human gate.

### Required GitHub configuration

- **Secrets:** Azure OIDC (`client-id`, `tenant-id`, `subscription-id`), `TF_VAR_db_admin_password`,
  `SWA_DEPLOYMENT_TOKEN`, and the Entra `TF_VAR_azure_ad_*` values.
- **Variables:** `ACR_NAME`, `CONTAINER_APP_NAME`, `RESOURCE_GROUP`, `TF_ENV` (default `prod`),
  `API_BASE_URL`, `FRONTEND_URL`, `AZURE_AD_CLIENT_ID`, `AZURE_AD_AUTHORITY`, `API_SCOPE`.

## 4. Containers

- **Backend** (`backend/Dockerfile`): multi-stage on digest-pinned `python:3.12-slim`; runs as non-root
  `appuser`; entrypoint `start.sh` runs `alembic upgrade head` then Uvicorn on port 8000;
  `HEALTHCHECK` hits `/api/v1/health`.
- **Frontend** (`frontend/Dockerfile`): build stage (`node:20-alpine`, `npm ci && npm run build`) →
  runtime `nginx:alpine` as non-root on port 8080 with SPA fallback to `index.html`. (Static Web Apps
  is the production host; the container image is available for container-based hosting.)

## 5. First-time provisioning with azd

`azure.yaml` wires the **Azure Developer CLI (azd)** to Terraform and the two services (`api` →
Container App, `web` → Static Web App). Provisioning hooks:

- **preprovision** (`scripts/preprovision.*`) — generates a strong 32-char DB admin password if not set.
- **postprovision** (`scripts/postprovision.*`) — creates/configures the Entra ID app registration,
  the `access_as_user` OAuth scope and service principal, and stores client/tenant IDs in the azd
  environment; prompts for admin consent.

```bash
azd auth login
azd env new rmp-prod
azd up                      # provision infra + deploy both services
```

> **Deployment policy for this project:** routine deploys go through **Azure Cloud Shell**, not a local
> Windows terminal. Run `az`/`azd`/Terraform commands from Cloud Shell (or let GitHub Actions perform
> the deploy). Always check existing Azure resources before creating new ones.

## 6. Database migrations on deploy

Migrations are **not** a separate pipeline step in GitHub Actions — the backend container runs
`alembic upgrade head` on startup (`start.sh`). A new revision therefore applies pending migrations as
it boots. Author migrations so they are safe to run against the live schema (additive first; avoid
destructive changes in the same release as the code that depends on the old shape).

## 7. Rollback

- **Backend:** automatic — the deploy job redirects traffic to the previous Container App revision and
  deactivates the new one if the post-deploy health check fails. To roll back manually, shift 100% of
  traffic back to the prior revision (revisions are suffixed with a timestamp for traceability).
- **Frontend:** redeploy the previous build artifact / commit to Static Web Apps.
- **Infrastructure:** revert the Terraform change and re-apply. Note the audit-log WORM lock is
  irreversible once enabled.

## 8. Smoke checks after deploy

1. `GET {API_BASE_URL}/health` → `200`, expected version.
2. `GET {API_BASE_URL}/health/ready` → `healthy` (DB, Search, OpenAI, Storage all green).
3. Load the frontend URL, sign in with Entra ID, confirm the chat page renders and a message round-trips
   with citations.
4. Confirm an audit entry was written for the test action (admin → Audit log).

See [operations-runbook.md](../operations/operations-runbook.md) for monitoring and incident response.
</content>
