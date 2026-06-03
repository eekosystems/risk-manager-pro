# Data Model

The backend uses **SQLAlchemy 2.0 (async)** over **Azure Database for PostgreSQL** with the
**pgvector** extension. Models live in `backend/app/models/`. Schema changes are applied exclusively
through **Alembic** migrations (`backend/alembic/versions/`, currently `001`–`029`).

> **Tenant isolation rule:** every org-scoped table carries an indexed `organization_id`. All
> repository queries filter on it. Treat any query without an `organization_id` (or `tenant_id`) filter
> on org-scoped data as a bug.

## Entity-relationship summary

```
User ──< OrganizationMembership >── Organization
 │                                      │
 │                                      ├──< RiskEntry ──< Mitigation
 │                                      │        │
 │                                      │        └──< ClosureApproval
 │                                      ├──< Conversation ──< Message
 │                                      ├──< Document
 │                                      ├──< Workflow
 │                                      ├──< Notification ──< NotificationDeliveryLog
 │                                      ├──< OrganizationSettings
 │                                      └──< AuditEntry
 │
 └──< UserNotificationPreference

Dual risk register (platform-level):
  RiskRecordLink (fg_risk ↔ client_risk)
  PendingSyncChange ── reviewed by analysts
  AirportContextProfile ──< ACPIntelligenceItem
```

## Identity & tenancy

### `users`
Azure AD-backed identities, auto-provisioned on first authenticated request.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `entra_id` | str, unique, indexed | Azure AD object ID (OID claim) |
| `email` | str, unique | |
| `display_name` | str | |
| `is_platform_admin` | bool, default false | Faith Group staff super-user flag |
| `is_active` | bool, default true | |
| `invitation_status` | str | `ACTIVE` \| `INVITED` \| `PROVISIONED` |
| `created_at`, `last_login`, `last_activity` | datetime | Login/activity throttled to ~5-min granularity |

### `organizations`
A tenant. Faith Group's own org has `is_platform = true`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `name` | str | |
| `slug` | str, unique, indexed | URL-safe identifier |
| `status` | enum | `ACTIVE` \| `SUSPENDED` \| `ARCHIVED` |
| `is_platform` | bool | Marks the Faith Group platform org |
| `settings_json` | JSONB | Org-level config |
| `created_by` | UUID FK→users | |

### `organization_memberships`
Join table that also carries the **role** (the basis for RBAC).

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID FK, indexed | |
| `organization_id` | UUID FK, indexed | |
| `role` | enum | `ORG_ADMIN` \| `ANALYST` \| `VIEWER` |
| `is_active` | bool | |
| `invited_by` | UUID FK→users | |
| unique | `(user_id, organization_id)` | One membership per user per org |

## Risk management

### `risk_entries`
The central safety record. Carries both a "classic" set of fields and a rich **risk-register**
extension set (added for the airport risk-register workflow).

Core fields:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `organization_id` | UUID FK, indexed | Tenant scope |
| `created_by` | UUID FK→users | |
| `title`, `description`, `hazard` | str/text | |
| `severity` | int 1–5 | Minimal → Catastrophic |
| `likelihood` | str A–E | Frequent → Extremely Improbable |
| `risk_level` | enum | `LOW` \| `MEDIUM` \| `HIGH` (computed from the FAA 5×5 matrix) |
| `status` | enum | `OPEN` \| `MITIGATING` \| `CLOSED` \| `ACCEPTED` (legacy lifecycle) |
| `function_type` | str | `general` \| `phl` \| `sra` \| `system` \| `risk_register` |
| `conversation_id` | UUID FK→conversations (SET NULL) | Provenance link to the chat that created it |
| `notes` | text | |

Risk-register extension fields:

| Column | Type | Notes |
|--------|------|-------|
| `airport_identifier` | str, indexed | e.g., an airport code |
| `potential_credible_outcome` | text | |
| `operational_domain` | enum | movement_area / non_movement_area / ramp / terminal / landside / user_defined |
| `sub_location` | str | |
| `hazard_category_5m` | enum | human / machine / medium / mission / management |
| `hazard_category_icao` | enum | technical / human / organizational / environmental |
| `risk_matrix_applied` | enum | airport_specific / faa_5x5 / conservative_default |
| `existing_controls` | text | |
| `residual_risk_level` | enum | LOW / MEDIUM / HIGH |
| `record_status` | enum | OPEN / IN_PROGRESS / PENDING_ASSESSMENT / CLOSED / MONITORING |
| `validation_status` | enum | RMP_VALIDATED / USER_REPORTED / PENDING |
| `source` | enum | rmp_sp1–4 / manual_entry / fg_push / client_push |
| `sync_status` | enum | FG_ONLY / CLIENT_ONLY / DUAL_IN_SYNC / DUAL_PENDING |
| `acm_cross_reference` | text | |
| `related_record_ids` | UUID[] | |
| `audit_trail_json` | JSONB | Embedded change history |

### `mitigations`
Child of a risk entry (cascade delete).

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `risk_entry_id` | UUID FK, indexed, CASCADE | |
| `title`, `description` | str/text | |
| `assignee` | str | |
| `due_date`, `completed_at` | datetime | |
| `verification_method` | text | |
| `status` | enum | `PENDING` \| `IN_PROGRESS` \| `COMPLETED` \| `CANCELLED` |

### `airport_sub_locations`
Lookup of named sub-locations per airport, unique on `(organization_id, airport_identifier, name)`.

## Chat & documents

### `conversations`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id`, `organization_id` | UUID FK, indexed | Owner + tenant |
| `title` | str | Defaults to "New Conversation" |
| `function_type` | enum | PHL / SRA / SYSTEM_ANALYSIS / GENERAL / RISK_REGISTER |
| `status` | enum | ACTIVE / ARCHIVED |

### `messages`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `conversation_id` | UUID FK, indexed, CASCADE | |
| `role` | enum | USER / ASSISTANT / SYSTEM |
| `content` | text | |
| `citations` | JSONB[] | RAG citations: `{doc_id, chunk_idx, snippet}` |
| `metadata_json` | JSONB | function_type, token counts, etc. |

### `documents`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `organization_id` | UUID FK, indexed | Tenant scope |
| `uploaded_by` | UUID FK→users | |
| `filename`, `content_type`, `size_bytes` | | |
| `blob_path` | str | Azure Blob Storage location |
| `folder_path` | str | SharePoint hierarchy (if crawled) |
| `status` | enum | UPLOADED / PROCESSING / INDEXED / FAILED |
| `source_type` | enum | CLIENT / FAA / ICAO / EASA / NASA_ASRS / INTERNAL |
| `chunk_count` | int | Number of indexed chunks |
| `content_hash` | str (SHA-256), indexed | Deduplication |
| `error_message` | text | Populated on FAILED |

> The chunk text + embeddings themselves live in **Azure AI Search**, not PostgreSQL. See
> [rag-pipeline.md](rag-pipeline.md) for the search index schema.

## Workflows

### `workflows`
PHL / SRA workflow instances with an approval state machine.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `organization_id`, `created_by` | UUID FK | |
| `type` | enum | `PHL` \| `SRA` |
| `status` | enum | `DRAFT` → `SUBMITTED` → `APPROVED` / `REJECTED` |
| `title` | str | |
| `data` | JSONB | Form data |
| `conversation_id` | UUID FK (SET NULL) | Source chat |
| `risk_entry_id` | UUID FK (SET NULL) | Resulting risk, if promoted |
| `submitted_at`, `approved_at`, `approved_by` | | Approval audit fields |

## Notifications

### `notifications`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `organization_id`, `recipient_user_id`, `triggered_by_user_id` | UUID FK, indexed | |
| `type` | enum, indexed | CHAT_RESPONSE / RISK_CREATED / RISK_UPDATED / MITIGATION_CREATED / DOCUMENT_INDEXED / RISK_THRESHOLD_EXCEEDED / SYNC_PENDING_REVIEW / ACP_FLAG_RAISED / CLOSURE_APPROVAL_REQUESTED / CLOSURE_APPROVAL_DECIDED |
| `title`, `body` | str/text | Bodies deliberately avoid sensitive content; link to the resource instead |
| `resource_type`, `resource_id` | | |
| `is_read` | bool, indexed | |

### `notification_delivery_log`
Per-channel delivery record (`IN_APP` / `EMAIL`) with status `PENDING` / `SENT` / `FAILED` / `SKIPPED`.

### `user_notification_preferences`
`user_id` PK, `email_opt_out` bool. Updatable without login via a signed preference token.

## Settings

### `organization_settings`
Per-org, per-category configuration. `category` ∈ `rag` / `model` / `prompts` / `qaqc`, with the actual
config in `settings_json`.

## Audit

### `audit_log`
Append-only SOC 2 audit trail. See [security-compliance.md](../operations/security-compliance.md).

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `timestamp` | datetime, indexed | |
| `user_id` | UUID FK, indexed | |
| `action` | str, indexed | e.g., `risk.created`, `document.uploaded` |
| `resource_type` | str | `risk_entry`, `document`, … |
| `resource_id` | str | |
| `ip_address` | str(45) | IPv6-safe |
| `user_agent` | str(500) | |
| `correlation_id` | UUID, indexed | Ties entries to a request trace |
| `outcome` | str | `success` / `failure` / `denied` |
| `metadata_json` | JSONB | |
| `organization_id` | UUID FK, indexed | Scopes audit queries |

Migration `028_audit_log_append_only` adds the append-only enforcement; entries are never updated or
deleted in normal operation.

## Dual risk register (platform-level sync)

These tables power synchronization between Faith Group's copy of a risk and the client's copy.

- **`risk_record_links`** — pairs `fg_risk_entry_id` ↔ `client_risk_entry_id` for an
  `airport_identifier`, status `ACTIVE` / `BROKEN`, unique on the pair.
- **`pending_sync_changes`** — a proposed change (`CREATE` / `UPDATE` / `CLOSE`) flowing
  `CLIENT_TO_FG` or `FG_TO_CLIENT`, with a `diff_json` (`{field: {old, new}}`), status
  `PENDING` / `ACCEPTED` / `REJECTED`, and reviewer fields. Analysts review the queue and accept/reject.
- **`airport_context_profiles`** (ACP) — per-airport intelligence owned by the platform org
  (system profile, known risk factors, stakeholder notes, operational impact history). Unique per
  `(organization_id, airport_identifier)`.
- **`acp_intelligence_items`** — external safety signals (FAA incident, NASA ASRS, NOTAM, regulatory
  action, safety news, manual) attached to an ACP, with a `decision`
  (pending / accepted_new_record / accepted_linked / accepted_monitor / dismissed).
- **`closure_approvals`** — closure-approval gate for High risk records: a request and an
  Accountable-Executive decision (`PENDING` / `APPROVED` / `REJECTED`).

## Migrations

```bash
cd backend
alembic upgrade head            # apply all pending
alembic downgrade -1            # revert one
alembic revision -m "message"   # new (manual) migration
alembic history                 # revision tree
```

When you add a model, import it in `app/models/__init__.py` so Alembic autogenerate detects it. The
container runs `alembic upgrade head` on startup via `start.sh`. There are 29 migrations today; the
latest is `029_drop_extreme_risk_level` (the risk-level enum was narrowed to LOW/MEDIUM/HIGH).
</content>
