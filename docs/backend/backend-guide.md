# Backend Guide

The backend is a **Python 3.12 / FastAPI** service using **SQLAlchemy 2.0 (async)**, **Pydantic v2**,
and **Alembic**. It is packaged as a container and deployed to **Azure Container Apps**.

For setup and day-to-day commands, see the [Local Development Runbook](../runbooks/local-dev.md). This
guide explains how the backend is organized and where to make changes.

## 1. Layout

```
backend/app/
├── main.py            # App factory, middleware, lifespan, exception handlers
├── api/v1/            # Route handlers (thin controllers), one file per domain
│   └── router.py      # Aggregates all routers under /api/v1
├── core/
│   ├── config.py      # Settings (env vars), boot validators, computed properties
│   ├── auth.py        # Entra ID JWT validation (issuer/audience/tenant/JWKS)
│   ├── auth_throttle.py  # Failed-auth throttling (in-memory or Redis)
│   ├── database.py    # Async engine + session factory
│   ├── deps/          # FastAPI dependencies (auth, organization/RBAC, services, common)
│   ├── exceptions.py  # AppError + structured error handling
│   ├── middleware.py  # Correlation-ID ASGI middleware
│   ├── logging.py     # structlog configuration
│   ├── telemetry.py   # Azure Monitor / OpenTelemetry
│   ├── rate_limit.py  # slowapi limiter
│   └── tasks.py       # Background task tracking + graceful drain
├── models/            # SQLAlchemy ORM models
├── repositories/      # Data-access layer (ALL queries live here)
├── schemas/           # Pydantic request/response models + envelopes (common.py)
├── services/          # Business logic
└── utils/
```

## 2. The layered rule

```
api/  →  services/  →  repositories/  →  models/
```

- **Controllers (`api/`)** validate input, enforce auth/role via `Depends()`, call one service, return.
  No business logic, no direct DB access.
- **Services (`services/`)** hold business logic and orchestration. They call repositories and external
  services and emit audit entries.
- **Repositories (`repositories/`)** own every database query. **Always scope by `organization_id`.**
- **Models (`models/`)** are the ORM definitions; see [data-model.md](../architecture/data-model.md).

Dependencies are wired in `core/deps/`. Services are constructed in `core/deps/services.py` and a
`ServiceRegistry` of long-lived clients (Azure OpenAI, RAG, Blob, Search, Graph, SharePoint crawler,
risk-outcome importer) is built at startup.

## 3. App bootstrap (`main.py`)

**Middleware (outer → inner):** Correlation-ID → CORS.

**Exception handlers:**
- `RateLimitExceeded` → 429 envelope
- `AppError` → structured `{ "error": { code, message } }` at the error's status code
- `Exception` (catch-all) → 500 with correlation ID, no stack trace leaked to the client

**Lifespan / startup:**
- Configure structlog and telemetry.
- Build the `ServiceRegistry`.
- Start background workers: the QA/QC email digest worker and a risk-outcome pre-warm scan.
- Validate production safety (CORS wildcard check, etc.).

**Lifespan / shutdown:**
- `drain_all_tasks()` awaits in-flight background tasks (so audit/notification writes flush).
- Close the email service and all registry clients.

## 4. Configuration (`core/config.py`)

All configuration comes from environment variables (Pydantic `BaseSettings`). Highlights:

**Application**
| Var | Default | Purpose |
|-----|---------|---------|
| `APP_ENV` | `development` | `development` \| `production` |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed origins (JSON array or CSV) |
| `SESSION_TIMEOUT_MINUTES` | `60` | Idle session timeout |

**Auth / rate limiting**
| Var | Default | Purpose |
|-----|---------|---------|
| `AUTH_LOCKOUT_THRESHOLD` | `5` | Failed attempts before IP lockout |
| `AUTH_LOCKOUT_WINDOW_MINUTES` | `15` | Lockout window |
| `RATE_LIMIT_DEFAULT` / `_AI` / `_AUTH` | `200/min` / `30/min` / `30/min` | Limits |
| `RATE_LIMIT_STORAGE_URI` | `""` | Redis URL for distributed limiting (empty = in-memory) |
| `ENFORCE_RBAC` | `true` | Enforce role checks (production refuses to boot if `false`) |

**Data / Azure**
| Var | Default | Purpose |
|-----|---------|---------|
| `DATABASE_URL` | *(required)* | Async Postgres URL; `sslmode=` auto-converted to `ssl=` for asyncpg |
| `AZURE_OPENAI_ENDPOINT` / `_DEPLOYMENT_NAME` / `_EMBEDDING_DEPLOYMENT` / `_API_VERSION` | – / `gpt-4o` / `text-embedding-3-small` / `2024-10-21` | Azure OpenAI |
| `AZURE_SEARCH_ENDPOINT` / `_INDEX_NAME` | – / `rmp-documents` | Azure AI Search |
| `AZURE_STORAGE_ACCOUNT_NAME` / `_CONTAINER_NAME` / `_AUDIT_CONTAINER` | – / `documents` / `audit-logs` | Blob Storage |
| `AZURE_AD_TENANT_ID` / `_CLIENT_ID` | – | Entra ID (tenant required in production) |
| `AZURE_DOC_INTELLIGENCE_ENDPOINT` / `_KEY` | – | OCR fallback |
| `ACS_ENDPOINT` / `_SENDER_ADDRESS` / `_REPLY_TO_ADDRESS` | – | Email (Azure Communication Services) |

**RAG / processing**
| Var | Default | Purpose |
|-----|---------|---------|
| `CHUNK_SIZE_TOKENS` / `CHUNK_OVERLAP_TOKENS` | `500` / `50` | Chunking |
| `MAX_FILE_SIZE_BYTES` | `250 MiB` | Upload cap |
| `EMBEDDING_BATCH_SIZE` / `SEARCH_INDEX_BATCH_SIZE` | `100` / `100` | Batching |
| `PROCESSING_CONCURRENCY` | `5` | Concurrent doc processing |
| `CHAT_SMART_ROUTING` | `true` | Function-type auto-routing |

**Observability / misc**
| Var | Default | Purpose |
|-----|---------|---------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `""` | App Insights (no-op locally) |
| `OTEL_SERVICE_NAME` / `OTEL_TRACES_SAMPLER_ARG` | `risk-manager-pro-api` / `1.0` | Tracing |
| `QAQC_DIGEST_ENABLED` / `_SEND_HOUR_UTC` | `true` / `13` | QA/QC digest worker |
| `QAQC_PREFERENCE_TOKEN_SECRET` | `""` | HMAC secret for opt-out tokens (≥32 chars in prod) |

**Production boot validators** (fail fast on misconfiguration): require `DATABASE_URL`; refuse
`ENFORCE_RBAC=false`; require `AZURE_AD_TENANT_ID`; forbid wildcard `CORS_ORIGINS`; require a
≥32-char preference-token secret.

## 5. Services tour (`services/`)

| Service | Responsibility |
|---------|----------------|
| `chat.py` | Chat orchestration: routing, RAG retrieval, LLM call, citations, streaming |
| `rag.py` | Hybrid search over Azure AI Search; tenant filter; `top_k` cap; injection defenses |
| `routing.py` | Function-type classification (regex + small-model fallback) |
| `prompts.py` | System/function prompt templates |
| `openai_client.py` | Async Azure OpenAI client (chat, embeddings) |
| `document.py` | Document CRUD + status |
| `document_processor.py` | Extraction → OCR/vision → chunking → embedding → indexing |
| `parser_sandbox.py` | Resource-capped subprocess for untrusted file parsing |
| `search_indexer.py` / `search_schema.py` | Azure AI Search index management |
| `storage.py` | Azure Blob Storage client |
| `risk.py` | Risk + mitigation logic; threshold evaluation; RR sync hooks |
| `risk_threshold.py` | Per-org risk-count threshold evaluation + notifications |
| `risk_outcome_importer.py` | Parse SharePoint risk-outcome data; classification rules |
| `rr_sync.py` / `rr_tools.py` | Dual risk-register linking, change queue, closure gate |
| `workflow.py` | PHL/SRA workflow state machine |
| `organization.py` | Org + membership management; Graph invitations |
| `notification.py` | In-app + email notification dispatch; opt-out |
| `email.py` / `email_templates/` | ACS email send + templating |
| `microsoft_graph.py` | Graph API: user lookup, invitations, drive/file discovery, downloads |
| `sharepoint_crawler.py` | SharePoint discovery/traversal/download |
| `analytics.py` | Dashboard aggregations |
| `audit.py` / `audit_query.py` | Audit write path + query/export |
| `digest_worker.py` | Daily QA/QC email digest worker |
| `preference_tokens.py` | HMAC opt-out tokens |
| `settings.py` | Org settings CRUD |

## 6. Errors, logging, and audit

- **Errors:** raise `AppError(code, message, status_code)` from services; the handler renders the
  structured envelope. Never expose stack traces or internal messages to clients.
- **Logging:** use `structlog`, never `print()`. The correlation ID and organization ID are bound
  automatically; pass `user_id` and an `alert_category` where relevant. No PII in logs (log `user_id`,
  not email/name).
- **Audit:** inject the audit logger into state-changing handlers and log every mutation. The write is
  fire-and-forget (async task) and tracked so it drains on shutdown. See
  [security-compliance.md](../operations/security-compliance.md).

## 7. Testing

`pytest` with async support. Service tests run against a real PostgreSQL (pgvector) — do **not** mock
the database. CI also runs `ruff` (lint + format), `mypy` (type check), `bandit` (SAST), and
`pip-audit`. Target ≥80% coverage on the services layer.

```bash
cd backend
pytest                          # full suite (needs docker-compose Postgres up)
pytest tests/api/test_rbac.py   # focused
make lint && make type-check    # match CI locally
```

## 8. Operational scripts (`backend/scripts/`)

| Script | Purpose |
|--------|---------|
| `seed.py` | Idempotent demo/seed data (`python -m scripts.seed`) |
| `backfill_memberships.py` | Backfill org memberships before enabling RBAC enforcement |
| `load_regulatory.py` | Load regulatory reference documents |

The container entrypoint `start.sh` runs `alembic upgrade head` and then launches Uvicorn.
</content>
