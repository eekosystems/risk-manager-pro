# Architecture Overview

## 1. System context

Risk Manager Pro is a multi-tenant web application. Three classes of users (scoped by role within an
organization) interact with it:

- **Viewers** — read-only access to risks, conversations, documents, and analytics.
- **Analysts** — create and modify risks, mitigations, documents, and run AI chat/workflows.
- **Org admins** — everything an analyst can do, plus manage members, settings, and view audit logs.
- **Platform admins** (Faith Group staff) — cross-organization visibility, dual-register sync review, and airport context management.

Authentication is delegated to **Microsoft Entra ID** (Azure AD). The application is **single-tenant
at the identity level** (one Entra tenant) but **multi-tenant at the data level** (many client
organizations, isolated by `organization_id`).

## 2. Component diagram

```
                          ┌─────────────────────────────┐
                          │      Microsoft Entra ID      │
                          │   (OIDC / OAuth2, JWT)       │
                          └──────────────┬──────────────┘
                                         │ tokens
            ┌────────────────────────────┼────────────────────────────┐
            │                            │                             │
   ┌────────▼─────────┐        ┌─────────▼──────────┐                  │
   │  Frontend (SPA)  │  HTTPS │   Backend API      │                  │
   │  React + Vite    │───────▶│   FastAPI          │                  │
   │  Azure Static    │  /api  │   Azure Container  │                  │
   │  Web Apps        │◀───────│   Apps             │                  │
   └──────────────────┘  JSON  └───┬───┬───┬───┬────┘                  │
                                    │   │   │   │                       │
              ┌─────────────────────┘   │   │   └───────────────┐       │
              │           ┌─────────────┘   └──────┐            │       │
     ┌────────▼────────┐  │  ┌──────────────────┐  │  ┌─────────▼─────┐ │
     │ PostgreSQL      │  │  │ Azure OpenAI     │  │  │ Azure AI      │ │
     │ Flexible Server │  │  │ GPT-4o + embed   │  │  │ Search        │ │
     │ (+ pgvector)    │  │  └──────────────────┘  │  │ (hybrid)      │ │
     └─────────────────┘  │                        │  └───────────────┘ │
              ┌───────────▼──────┐    ┌────────────▼─────┐              │
              │ Azure Blob       │    │ Azure Comm.      │              │
              │ Storage          │    │ Services (email) │              │
              │ docs + audit-logs│    └──────────────────┘              │
              └──────────────────┘                                      │
                                                                        │
     ┌──────────────────────────────────────────────────────┐          │
     │ Microsoft Graph / SharePoint (document source crawl)  │◀─────────┘
     └──────────────────────────────────────────────────────┘

   Secrets: Azure Key Vault (accessed via Managed Identity)
   Observability: Azure Monitor + Application Insights + Log Analytics
```

## 3. Repository layout (monorepo)

```
risk-manager-pro/
├── frontend/             # React + TypeScript SPA (Vite)
├── backend/              # Python FastAPI service
│   ├── app/
│   │   ├── api/v1/        # Route handlers (thin controllers)
│   │   ├── core/          # Config, auth, deps, middleware, logging, telemetry
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── repositories/  # Data-access layer (all DB queries)
│   │   ├── schemas/       # Pydantic request/response models
│   │   ├── services/      # Business logic
│   │   └── utils/
│   ├── alembic/versions/  # 29 database migrations (001–029)
│   ├── scripts/           # seed, backfill_memberships, load_regulatory
│   └── tests/
├── infra/                # Terraform IaC (root + 10 modules)
├── azure-pipelines.yml   # Azure DevOps Pipelines (canonical CI/CD)
├── azure.yaml            # Azure Developer CLI (azd) service/infra wiring
├── docker-compose.yml    # Local Postgres (pgvector) + Azurite
├── Makefile              # Dev shortcuts
└── docs/                 # This documentation
```

See [backend-guide.md](../backend/backend-guide.md) and
[frontend-guide.md](../frontend/frontend-guide.md) for per-tier detail.

## 4. Backend layering

The backend follows a strict layered architecture. **Data flows downward; never skip a layer.**

```
HTTP request
   │
   ▼
api/v1/*.py        Thin controllers: validate input, enforce auth/role, call a service, return.
   │               No business logic here.
   ▼
services/*.py      Business logic: orchestration, rules, calling external services, audit.
   │
   ▼
repositories/*.py  All database queries. Always scoped by organization_id (tenant isolation).
   │
   ▼
models/*.py        SQLAlchemy ORM (PostgreSQL).
```

Cross-cutting concerns are injected via FastAPI `Depends()`:

- **Auth & current user** — `app/core/deps/auth.py`
- **Organization context & RBAC** — `app/core/deps/organization.py`
- **Services** — `app/core/deps/services.py`
- **Audit logger** — injected into state-changing handlers

## 5. Request lifecycle

1. **Correlation ID middleware** (`app/core/middleware.py`) — assigns/propagates `X-Correlation-ID`
   and binds `correlation_id` + `organization_id` into the structured-logging context. Implemented as
   pure ASGI middleware so error responses still carry the correlation ID.
2. **CORS middleware** — origins configured per environment; wildcard origins are blocked in production.
3. **Rate limiting** (`app/core/rate_limit.py`, slowapi) — 200/min default, 30/min for AI/chat and auth
   endpoints. Health checks are exempt. Backed by in-memory store (single instance) or Redis (set
   `RATE_LIMIT_STORAGE_URI` for multi-instance).
4. **Authentication** (`app/core/deps/auth.py`) — validates the Entra ID JWT, resolves/auto-provisions
   the `User`, enforces the 60-minute idle session timeout, and throttles failed attempts per IP.
5. **Authorization** (`app/core/deps/organization.py`) — resolves the active organization (from the
   `X-Organization-ID` header) and checks the caller's role.
6. **Handler → service → repository** executes the work.
7. **Audit logging** — state-changing handlers fire an audit entry (async, fire-and-forget; see
   [security-compliance.md](../operations/security-compliance.md)).
8. **Response envelope** — successful responses are wrapped in `DataResponse[T]` or
   `PaginatedResponse[T]`; errors in a structured `{ "error": { "code", "message" } }` envelope.

## 6. Core domains

| Domain | Backend router | Key models | Notes |
|--------|----------------|------------|-------|
| Chat / RAG | `chat.py` | Conversation, Message | Streaming (SSE) and non-streaming; smart routing to function types |
| Documents | `documents.py` | Document | Upload → background processing → Azure AI Search index |
| Risks | `risks.py` | RiskEntry, Mitigation | FAA 5×5 matrix; threshold notifications |
| Workflows | `workflows.py` | Workflow | PHL / SRA state machine (DRAFT→SUBMITTED→APPROVED/REJECTED) |
| Organizations | `organizations.py` | Organization, OrganizationMembership | Membership + RBAC |
| Risk-register sync | `rr_sync.py` | RiskRecordLink, PendingSyncChange, AirportContextProfile, … | Dual-register Faith Group ↔ client sync |
| Analytics | `analytics.py` | (aggregations) | Dashboard KPIs + activity feed |
| Audit | `audit.py` | AuditEntry | Admin-only; list, filter, CSV export |
| Notifications | `notifications.py` | Notification, …Preference | In-app + email; token-based opt-out |
| Settings | `settings.py` | OrganizationSettings | RAG / model / prompts / QAQC config |
| Search | `search.py` | (cross-entity) | Full-text over conversations + documents |
| SharePoint | `sharepoint.py` | (ingest source) | Crawl client document libraries |

See the full endpoint catalog in [api-reference.md](../api/api-reference.md), the schema in
[data-model.md](data-model.md), and the AI pipeline in [rag-pipeline.md](rag-pipeline.md).

## 7. The chat-centric UX

The product deliberately centers on chat. The frontend's primary screen is the chat page; risk-register,
analytics, audit-log, and the PHL/SRA workflows are secondary views. Five **function types** shape each
chat turn:

- `general` — freeform Q&A (default)
- `phl` — Preliminary Hazard List (hazard identification)
- `sra` — Safety Risk Assessment (hazard scoring)
- `system` — system analysis
- `risk_register` — structured hazard entry into the airport risk register (tool-calling mode)

The backend can **auto-route** an incoming message to the most appropriate function type
(`CHAT_SMART_ROUTING`, on by default). Legacy standalone PHL/SRA **form wizards** still exist in the
codebase but are reachable only by analysts/admins from the workflow views — the chat flow is the
primary path.

## 8. Key cross-cutting principles

- **Tenant isolation** — every repository query filters by `organization_id`; the RAG layer filters
  Azure AI Search by `tenant_id`. There is no global, unscoped data access path for org data.
- **Audit everything that changes state** — append-only, dual-written to PostgreSQL and immutable Blob storage.
- **No secrets in code** — all secrets come from Key Vault via Managed Identity; environment variables
  carry only non-sensitive config.
- **Structured logging** — JSON logs with a correlation ID on every request; no `print()`.
- **Fail safe in production** — boot validators refuse to start production with RBAC disabled, a wildcard
  CORS origin, a missing tenant ID, or a weak token secret.
</content>
