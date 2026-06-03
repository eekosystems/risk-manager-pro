# Security & Compliance

Risk Manager Pro is built to **SOC 2 Type II** and **NIST SP 800-171 (CUI)** expectations. This
document describes the security controls as implemented in code and infrastructure, and the status of
the security audit. The mandatory patterns themselves are in
[../../ENGINEERING_STANDARDS.md](../../ENGINEERING_STANDARDS.md) — follow them on every change.

## 1. Authentication (CC6.1)

Implemented in `app/core/auth.py` and `app/core/deps/auth.py`.

- **Token source:** Microsoft Entra ID JWTs (RS256). Validated for **signature** (against JWKS),
  **issuer** (both v2.0 `login.microsoftonline.com/{tenant}/v2.0` and v1.0 `sts.windows.net/{tenant}/`
  forms), **audience** (`{client_id}` and `api://{client_id}`), and **expiry**.
- **JWKS caching:** keys fetched from the tenant discovery endpoint, cached 24h, force-refreshed on an
  unknown `kid`.
- **Tenant pinning (defense in depth):** the token `tid` claim is checked against the configured tenant —
  foreign-tenant tokens are rejected even if otherwise valid.
- **User provisioning:** on first valid token, a `User` is auto-created (defaulting to VIEWER) and linked
  to an organization membership.
- **Idle session timeout:** 60 minutes. An idle session with a stale token is rejected (401); a fresh
  token (from MSAL silent refresh) re-establishes the session. The frontend warns before logout.
- **Failed-auth throttling:** per-IP, default 5 failures / 15-minute window → `429` lockout
  (`app/core/auth_throttle.py`; in-memory single-instance, Redis multi-instance). Failures are logged
  with source IP.

## 2. Authorization & RBAC (CC6.3)

Implemented in `app/core/deps/organization.py`.

- **Roles:** `VIEWER` < `ANALYST` < `ORG_ADMIN`, plus a platform-admin super-user flag.
- **Active organization** is resolved from the `X-Organization-ID` header; the caller must be an active
  member or the request is `403`.
- **Role gates:** `require_any_member`, `require_analyst_or_above`, `require_org_role(ORG_ADMIN)`,
  `require_platform_admin`. Platform admins bypass org-role checks.
- **Enforcement:** controlled by `ENFORCE_RBAC` (default `true`). **Production refuses to boot with RBAC
  disabled.** Before enabling RBAC for the first time, run
  `python -m scripts.backfill_memberships --all-orgs`.

## 3. Tenant isolation (CC6.3)

- Every repository query filters by `organization_id`.
- The RAG layer filters Azure AI Search by `tenant_id`; `top_k` is capped at 20; user-supplied source
  filters are validated and quote-escaped to prevent OData injection.
- Search-index deletes are organization-scoped.
- There is **no unscoped data path** for org data. Treat any new query lacking a tenant filter as a bug.

## 4. Audit logging (CC7.2, CC7.3)

Implemented in `app/services/audit.py`, `app/models/audit.py`, exposed via `app/api/v1/audit.py`.

- **Every state-changing action** emits an audit entry with: `timestamp`, `user_id`, `action`,
  `resource_type`, `resource_id`, `ip_address`, `user_agent`, `correlation_id`, `outcome`
  (success/failure/denied), `organization_id`, and optional `metadata_json`.
- **Append-only:** entries are inserted, never updated or deleted (enforced by migration
  `028_audit_log_append_only`).
- **Dual write:** PostgreSQL (queryable) **and** Azure Blob Storage as immutable JSON
  (`audit/{yyyy}/{mm}/{dd}/{correlation_id}-{action}-{ts}.json`, `overwrite=false`). The Blob container
  has a **WORM immutability policy** (locked in production).
- **Non-blocking:** the write is a tracked fire-and-forget async task, so it never blocks the request and
  is drained on shutdown.
- **Resilience:** a circuit breaker (default 5 failures / 60s) protects against Blob outages; an audit
  persistence failure logs `alert_category="soc2_audit_failure"`.
- **Access & export:** listing/filtering/CSV export is **ORG_ADMIN-only**; CSV export is
  formula-injection-safe and capped at 10,000 rows.

## 5. Data protection (CC6.1, CC6.7)

- **In transit:** HTTPS/TLS enforced end to end; Postgres requires `sslmode=require`; storage requires
  TLS 1.2+.
- **At rest:** Azure service-level AES-256; Blob versioning + soft delete; audit logs immutable.
- **Secrets:** no secrets in code or config. `DATABASE_URL` and the App Insights connection string live
  in **Key Vault**, surfaced to the app as Container App secret references via **Managed Identity**.
  Service-to-service access uses Managed Identity (`DefaultAzureCredential`) and least-privilege RBAC —
  including a custom send-only role for email.
- **No PII in logs:** log `user_id`, never email/name. Notification bodies deliberately avoid sensitive
  content and link to the resource instead.
- **Input validation:** Pydantic v2 models validate all input; SQLAlchemy parameterizes all queries; the
  frontend relies on React's escaping and never uses `dangerouslySetInnerHTML`.
- **Untrusted file parsing** runs in a **resource-capped subprocess** (address space + CPU limits) so a
  malicious document cannot exhaust or crash the API.

## 6. Network & infrastructure hardening

See [infrastructure.md](../deployment/infrastructure.md). Key points: private PostgreSQL (no public
access), storage with public access and shared-key auth disabled (OAuth only), deny-by-default network
ACLs on AI services, Key Vault in RBAC mode with purge protection, non-root hardened container images
(digest-pinned), and image vulnerability scanning (Trivy) plus IaC scanning (tfsec) in CI.

## 7. Production boot validators

The backend **refuses to start in production** if any of these hold (`app/core/config.py`):

- `ENFORCE_RBAC` is `false`.
- `AZURE_AD_TENANT_ID` is empty (single-tenant model).
- `CORS_ORIGINS` contains a wildcard.
- `QAQC_PREFERENCE_TOKEN_SECRET` is shorter than 32 characters.
- `DATABASE_URL` is missing.

This prevents silent security downgrades from a misconfigured deploy.

## 8. Change management (CC8.1)

- All infrastructure changes go through Terraform (no manual portal changes).
- All schema changes go through Alembic migrations.
- CI gates every merge: lint, type check, unit tests, dependency audit (`pip-audit`/`npm audit`), SAST
  (`bandit`), and IaC scan (`tfsec`). Deploys are gated on a successful CI run and a production approval,
  and the deploy auth uses GitHub OIDC (no long-lived cloud credentials).

## 9. Security audit status

The platform underwent a security audit. The remediation work hardened the areas above; concrete,
code-visible outcomes include:

- Secrets moved out of plaintext environment variables into Key Vault references.
- RBAC made fail-closed and enforced-by-default, with a production boot validator.
- Least-privilege RBAC for the API identity (e.g., send-only email role).
- Per-IP failed-auth throttling and AI/upload rate limiting.
- RAG `top_k` ceiling and OData-injection defenses; tenant-scoped index deletes.
- Audit-log append-only migration and WORM immutability locked in production.
- Resource-capped sandbox for untrusted document parsing.
- Reduced TTL + rate limiting on unauthenticated notification-preference tokens.
- CSV formula-injection protection on audit export.
- Pinned GitHub Actions and Dependabot; container and IaC scanning in CI.
- Digest-pinned, non-root container images; loopback-only local Postgres.

> **Authoritative tracking:** the audit report and the per-finding remediation status are tracked
> outside the source tree (the project owner holds the current "real vs. cost-deferred" status). A few
> items are **intentionally cost-deferred to go-live** — most notably the Postgres HA / GP-tier /
> geo-redundant-backup settings in `prod.tfvars`. Confirm these are flipped (and the audit's open items
> closed) before declaring production-ready. The audit's original verdict gated production; verify the
> current status with the owner rather than assuming closure.

## 10. Security checklist for new work

- [ ] New endpoints require auth and the correct role gate (only health checks are public).
- [ ] Every new query filters by `organization_id` / `tenant_id`.
- [ ] State-changing operations emit an audit entry.
- [ ] No secrets in code or committed config; use Key Vault + Managed Identity.
- [ ] Input validated with Pydantic; errors return the structured envelope (no stack traces).
- [ ] No PII in logs; no sensitive content in notification bodies.
- [ ] Dependencies and IaC pass `pip-audit`/`npm audit`/`bandit`/`tfsec` in CI.
</content>
