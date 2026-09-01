# Risk Manager Pro — Engineering Standards

## Project Overview
Risk Manager Pro is an AI-driven operational risk management platform for private aviation safety.
It integrates Azure OpenAI with a RAG pipeline over aviation safety documentation to support
hazard identification, risk assessment, mitigation tracking, and safety performance monitoring.

**Client:** Faith Group LLC
**Deployment:** Azure (Faith Group tenant)
**Compliance:** SOC 2 Type II, NIST SP 800-171 (CUI protections)

## Architecture

### Monorepo Structure
```
risk-manager-pro/
├── frontend/          # React + TypeScript (Azure Static Web Apps)
├── backend/           # Python FastAPI (Azure Container Apps)
│   ├── app/
│   │   ├── api/       # Route handlers (thin controllers)
│   │   ├── core/      # Config, security, dependencies
│   │   ├── models/    # SQLAlchemy/Pydantic models
│   │   ├── services/  # Business logic layer
│   │   ├── schemas/   # Request/response Pydantic schemas
│   │   └── utils/     # Pure utility functions
│   ├── tests/
│   ├── alembic/       # Database migrations
│   └── pyproject.toml
├── infra/             # Bicep or Terraform (IaC)
├── .github/workflows/ # CI/CD pipelines
└── docs/              # Architecture decisions, runbooks
```

### Tech Stack
- **Frontend:** React 18+, TypeScript (strict mode), Tailwind CSS, MSAL.js for auth
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic
- **Database:** Azure Database for PostgreSQL (Flexible Server)
- **Vector Search:** Azure AI Search (hybrid keyword + vector) — pgvector as fallback
- **LLM:** Azure OpenAI Service (GPT-4o for chat, text-embedding-3-small for embeddings)
- **Storage:** Azure Blob Storage
- **Auth:** Microsoft Entra ID (Azure AD) via OIDC/OAuth2
- **Secrets:** Azure Key Vault with Managed Identities
- **Monitoring:** Azure Monitor + Application Insights

## Code Standards — MANDATORY

### General Principles
- Write code as a senior engineer shipping to production for an aviation safety client.
- Every function should do one thing. Every module should have one reason to change.
- No dead code, no commented-out code, no TODOs in merged code.
- Prefer explicit over implicit. Prefer boring technology over clever tricks.
- All business logic lives in the `services/` layer, never in route handlers.
- Route handlers are thin: validate input, call service, return response.

### Python Backend
- **Type hints on every function signature.** No `Any` types unless absolutely unavoidable.
- Use `async def` for all route handlers and database operations.
- Pydantic v2 models for ALL request/response validation. Never trust raw input.
- SQLAlchemy 2.0 style with mapped_column. No legacy patterns.
- Database queries go through repository functions, not inline in services.
- Use dependency injection via FastAPI's `Depends()` for auth, db sessions, services.
- Exception handling: use structured error responses, never expose stack traces.
- Logging: use structured JSON logging (structlog). Include correlation_id on every request.

```python
# CORRECT: Thin controller, typed, dependency-injected
@router.post("/assessments", response_model=AssessmentResponse, status_code=201)
async def create_assessment(
    payload: CreateAssessmentRequest,
    current_user: User = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
    audit: AuditLogger = Depends(get_audit_logger),
) -> AssessmentResponse:
    result = await service.create(payload, current_user)
    await audit.log("assessment.created", resource_id=result.id, user=current_user)
    return result
```

### TypeScript Frontend
- **Strict TypeScript.** No `any` types. Enable all strict compiler options.
- Components: functional components only. Props interfaces defined explicitly.
- State management: React Query (TanStack Query) for server state, React context for UI state.
- API calls go through a typed API client layer, never inline fetch calls in components.
- Use custom hooks to encapsulate logic. Components should be mostly JSX.
- File naming: `kebab-case.tsx` for components, `use-kebab-case.ts` for hooks.
- All user-facing strings must support future i18n (no hardcoded strings in JSX where avoidable).

```typescript
// CORRECT: Typed API client
export async function createAssessment(
  payload: CreateAssessmentRequest
): Promise<AssessmentResponse> {
  const response = await apiClient.post<AssessmentResponse>("/assessments", payload);
  return response.data;
}

// CORRECT: Custom hook wrapping API
export function useCreateAssessment() {
  return useMutation({
    mutationFn: createAssessment,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assessments"] }),
  });
}
```

### Error Handling
- Backend: Return structured error responses with error codes, not raw messages.
- Frontend: Every API call has error handling. Show user-friendly messages.
- Never swallow exceptions silently. Log them with context.
- Use discriminated error types, not generic catch-all handlers.

```python
# CORRECT: Structured error response
class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

# In exception handler middleware
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
```

## SOC 2 Compliance — MANDATORY PATTERNS

These are not optional. Every piece of code must follow these patterns.

### 1. Audit Logging (Trust Services Criteria: CC7.2, CC7.3)
- **Every state-changing API call** must produce an audit log entry.
- Audit logs are **append-only**. Never update or delete audit records.
- Required fields: `timestamp`, `user_id`, `action`, `resource_type`, `resource_id`,
  `ip_address`, `user_agent`, `correlation_id`, `outcome` (success/failure).
- Audit logs go to both PostgreSQL (queryable) and Azure Blob Storage (WORM/immutable).
- The audit logging middleware must not block the request — fire-and-forget to a queue.

```python
class AuditEntry(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(default=func.now(), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str] = mapped_column(String(45))
    user_agent: Mapped[str] = mapped_column(String(500))
    correlation_id: Mapped[uuid.UUID] = mapped_column(index=True)
    outcome: Mapped[str] = mapped_column(String(20))  # "success" | "failure" | "denied"
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
```

### 2. Authentication & Authorization (CC6.1, CC6.2, CC6.3)
- All endpoints require authentication except health checks.
- Auth tokens come from Microsoft Entra ID. Validate issuer, audience, and expiry.
- Implement application-level RBAC with roles: `admin`, `analyst`, `viewer`.
- Service-to-service auth uses Managed Identities — **never store credentials in code or config files**.
- Session timeout: 60 minutes of inactivity.
- Failed auth attempts must be logged with source IP.

### 3. Data Protection (CC6.1, CC6.7)
- **Encryption at rest:** AES-256 via Azure service-level encryption + Key Vault managed keys.
- **Encryption in transit:** TLS 1.3 enforced. No HTTP fallback.
- **No PII in logs.** Sanitize user data before logging. Log user_id, never email/name.
- **No secrets in code.** Use Azure Key Vault via Managed Identity. Environment variables are acceptable
  only for non-sensitive configuration (port numbers, feature flags).
- **Input validation:** Validate and sanitize ALL user input. Use Pydantic models with constrained types.
- **SQL injection prevention:** Use parameterized queries only (SQLAlchemy handles this).
- **XSS prevention:** React handles this by default. Never use `dangerouslySetInnerHTML`.

### 4. Access Control (CC6.3)
- Principle of least privilege for all Azure RBAC assignments.
- Application RBAC enforced at the API layer via middleware.
- Tenant isolation: queries must always filter by `tenant_id`. Use a base query mixin.
- Document access: users can only access documents belonging to their tenant.

```python
# CORRECT: Tenant-scoped query — always filter by tenant
async def get_documents(
    db: AsyncSession, tenant_id: uuid.UUID, skip: int = 0, limit: int = 50
) -> list[Document]:
    stmt = (
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

### 5. Change Management (CC8.1)
- All infrastructure changes via IaC (Bicep/Terraform). No manual Azure portal changes.
- Database migrations via Alembic with explicit up/down migrations.
- CI/CD enforces: linting, type checking, unit tests, security scanning before merge.

### 6. Availability & Incident Response (A1.2)
- Health check endpoint at `/health` and `/health/ready` (checks DB, AI Search, OpenAI connectivity).
- Structured logging with correlation IDs for request tracing.
- Application Insights integration for APM, error tracking, and alerting.

## Testing Standards
- Backend: pytest with async support. Minimum 80% coverage on services layer.
- Frontend: Vitest + React Testing Library. Test user interactions, not implementation.
- Integration tests for RAG pipeline (document ingestion → embedding → retrieval → response).
- No mocking of the database in service tests — use a test PostgreSQL instance.

## Git Conventions
- Branch naming: `feat/`, `fix/`, `refactor/`, `infra/`, `docs/`
- Commit messages: conventional commits (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`)
- PRs require passing CI and at least one approval.
- Never commit secrets, .env files, or credentials. `.gitignore` must be comprehensive.

## API Design
- RESTful endpoints under `/api/v1/`.
- Consistent response envelope: `{ "data": ..., "meta": { "request_id": "..." } }`
- Error envelope: `{ "error": { "code": "RESOURCE_NOT_FOUND", "message": "..." } }`
- Pagination: cursor-based for large collections, offset-based for admin views.
- Rate limiting enforced at Azure API Management layer.
- API versioning via URL path (`/api/v1/`, `/api/v2/`).

## Domain-Specific Rules
- **Aviation safety terminology must be correct.** PHL = Preliminary Hazard List,
  SRA = Safety Risk Assessment, SMS = Safety Management System, SRM = Safety Risk Management.
- Risk matrices follow standard 5x5 severity/likelihood grids per FAA SMS guidelines.
- Regulatory references (FAR, ICAO Annex 19, EASA regulations) must be cited accurately.
- AI responses must include source citations linking back to indexed documents.
- AI must never fabricate safety data. If the RAG context doesn't support an answer, say so.

## Environment Configuration
All configuration via environment variables or Azure Key Vault. Required variables:
```
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT_NAME=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=

# Azure AI Search
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_INDEX_NAME=

# Database
DATABASE_URL=

# Azure Blob Storage
AZURE_STORAGE_ACCOUNT_NAME=
AZURE_STORAGE_CONTAINER_NAME=

# Azure AD / Entra ID
AZURE_AD_TENANT_ID=
AZURE_AD_CLIENT_ID=
AZURE_AD_AUTHORITY=

# Application
APP_ENV=development|staging|production
LOG_LEVEL=INFO
CORS_ORIGINS=
```

## What NOT To Do
- Do NOT use ChromaDB, FAISS, or any local vector database. Use Azure AI Search.
- Do NOT call OpenAI directly. Use Azure OpenAI Service only.
- Do NOT store any secrets, API keys, or connection strings in code or config files.
- Do NOT bypass authentication for any endpoint except health checks.
- Do NOT use `print()` for logging. Use structlog.
- Do NOT write raw SQL. Use SQLAlchemy ORM.
- Do NOT skip audit logging on any state-changing operation.
- Do NOT use `any` type in TypeScript or untyped `dict` returns in Python.
- Do NOT expose internal error details to API consumers.
- Do NOT commit `.env` files, even for development.
