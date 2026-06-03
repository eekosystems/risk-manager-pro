# Operations Runbook

How to monitor, troubleshoot, and respond to incidents for Risk Manager Pro in Azure. For deploys and
rollback see [deployment-runbook.md](../deployment/deployment-runbook.md); for security controls see
[security-compliance.md](security-compliance.md).

## 1. Health & readiness

| Endpoint | Use |
|----------|-----|
| `GET /api/v1/health` | Liveness — is the process up? Returns status + version. Used by the container `HEALTHCHECK` and the deploy health-gate. |
| `GET /api/v1/health/ready` | Readiness — are dependencies reachable? Checks **DB**, **Azure AI Search**, **Azure OpenAI**, **Blob Storage**, and reports **background-task failure counts**. Results cached 15s. |

Readiness status values:
- `healthy` — all dependencies OK.
- `degraded` — DB OK but a downstream service (Search/OpenAI/Storage) is failing.
- `unhealthy` — DB is down.

A `degraded` result means the app is up but AI features or document indexing may be impaired — check the
affected Azure service before assuming an app bug.

## 2. Observability

- **Structured logs (structlog → JSON):** every log line carries `correlation_id` and `organization_id`
  (bound by the correlation-ID middleware). Start any investigation from the **correlation ID** — it ties
  together the request, its logs, and its audit entry, and it is returned in the response headers and
  error envelopes.
- **Application Insights / Azure Monitor:** enabled when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set
  (it is, in Azure; it's a no-op locally). Auto-instruments FastAPI requests, SQLAlchemy, asyncpg, and
  outbound HTTPX (Azure OpenAI, AI Search, Graph). Trace sampling via `OTEL_TRACES_SAMPLER_ARG`.
- **Log Analytics:** all resource diagnostics (Key Vault, Storage, Postgres, ACR, OpenAI, Search, ACS)
  flow to the central workspace.
- **Alerting:** the monitoring module defines a critical action group and a metric alert that fires on
  **>10 failed requests in 15 minutes** (severity 1).

**Useful log signals** (search by `alert_category`):
- `soc2_audit_failure` — an audit entry failed to persist. Investigate immediately (compliance impact).
- `background_task_failure` — a fire-and-forget task (audit write, notification, doc processing) failed.
- `auth_failure` / auth lockout events — authentication problems or possible abuse.

## 3. Background workers

The app runs background work as tracked asyncio tasks (`app/core/tasks.py`):

- **Document processing** — extraction → embedding → indexing after upload/crawl.
- **QA/QC email digest worker** — daily at `QAQC_DIGEST_SEND_HOUR_UTC` (default 13:00 UTC ≈ 08:00
  Central) when `QAQC_DIGEST_ENABLED=true`.
- **Risk-outcome pre-warm scan** — preloads SharePoint risk-outcome data at startup.

Failures increment counters surfaced in `/health/ready`. On shutdown, `drain_all_tasks()` awaits
in-flight tasks so audit/notification writes flush. **For multi-instance scale-out**, set
`RATE_LIMIT_STORAGE_URI` (Redis) so rate limiting and auth throttling are shared across replicas.

## 4. Common scenarios

### Document stuck in `PROCESSING` / `FAILED`
1. Check the document's `error_message` (DB / `GET /documents/{id}`).
2. Look for `background_task_failure` logs by the document's correlation ID.
3. Verify Azure OpenAI (embeddings) and Azure AI Search are healthy (`/health/ready`).
4. Re-trigger with `POST /documents/{id}/reindex`, or `POST /documents/process-all` to requeue all
   non-indexed documents.
5. A malformed/oversized file may hit the parser sandbox's CPU/memory caps — expect a clean `FAILED`,
   not an API crash.

### Chat returns no/weak answers
1. Confirm the relevant documents are `INDEXED` for the **caller's organization** (tenant scope).
2. Confirm Azure OpenAI and AI Search are healthy.
3. Remember `top_k` is capped at 20 and retrieval is tenant-filtered — cross-org content is never
   returned.

### 401s / users logged out unexpectedly
1. The idle session timeout is 60 minutes; a fresh MSAL token re-establishes an idle session.
2. Stale MSAL tokens: clear `sessionStorage` in the browser.
3. Check `auth_failure` logs and whether the source IP hit the lockout threshold (5 failures / 15 min).
4. Verify `AZURE_AD_TENANT_ID` / `AZURE_AD_CLIENT_ID` match the Entra app registration.

### 403 / access denied
1. Confirm the user's **membership and role** in the target organization.
2. Confirm the request sends the correct `X-Organization-ID`.
3. In production, RBAC is always enforced; platform admins bypass org-role checks.

### Email not delivered
1. Check `notification_delivery_log` for the channel/status.
2. Verify ACS configuration (`ACS_ENDPOINT`, `ACS_SENDER_ADDRESS`).
3. Check the recipient's `email_opt_out` preference.

### Rate limited (429)
Default 200/min; 30/min on auth and AI/chat. For sustained multi-instance load, move to Redis-backed
limiting (`RATE_LIMIT_STORAGE_URI`).

## 5. Incident response (A1.2)

1. **Detect** — alert fires, `/health/ready` degraded, or error spike in App Insights.
2. **Scope** — grab the correlation ID(s); query logs and App Insights; check which dependency is
   implicated via `/health/ready`.
3. **Mitigate** — roll back the backend revision (see deployment runbook) if a release is implicated;
   for a failing dependency, check that Azure service's health and the app's RBAC/network access to it.
4. **Verify** — re-run the smoke checks; confirm audit entries are persisting (no `soc2_audit_failure`).
5. **Record** — capture the timeline and root cause. Audit logs are immutable and queryable for the
   forensic trail.

## 6. Routine operational tasks

| Task | How |
|------|-----|
| Enable RBAC enforcement after backfill | Run `python -m scripts.backfill_memberships --all-orgs`, then ensure `ENFORCE_RBAC=true` (default; mandatory in prod). |
| Load regulatory reference docs | `python -m scripts.load_regulatory` |
| Inspect audit trail | Admin UI → Audit log, or `GET /audit` (filters + CSV export). |
| Add an organization | `POST /organizations` (platform admin), then add members. |
| Scale the API | Adjust Container App min/max replicas in Terraform; add Redis for shared rate-limit/throttle state. |
</content>
