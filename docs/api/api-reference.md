# API Reference

All endpoints are served under the prefix **`/api/v1`**. Router wiring is in
`backend/app/api/v1/router.py`; handlers are the per-domain files in `backend/app/api/v1/`.

> **Live, authoritative spec:** the running service exposes an OpenAPI document. In non-production
> environments, browse the interactive docs at **`/docs`** (Swagger UI) and **`/redoc`**, or fetch
> **`/openapi.json`**. This page is a curated overview; the OpenAPI schema is generated from the code
> and is always exact.

## Conventions

### Authentication
Every endpoint requires a valid **Entra ID bearer token** except the health checks and the
token-authenticated notification-preference endpoints. Send:

```
Authorization: Bearer <access-token>
X-Organization-ID: <organization-uuid>   # selects the active tenant
X-Correlation-ID: <uuid>                  # optional; generated if absent
```

### Authorization (role gates)
Role requirements are enforced by FastAPI dependencies:

| Dependency | Allows |
|------------|--------|
| `get_current_user` | any authenticated user |
| `require_any_member` | VIEWER, ANALYST, ORG_ADMIN |
| `require_analyst_or_above` | ANALYST, ORG_ADMIN |
| `require_org_role(ORG_ADMIN)` | ORG_ADMIN |
| `require_platform_admin` | platform admins only |

### Response envelopes
```jsonc
// Single resource
{ "data": { ... }, "meta": { "request_id": "<correlation-id>" } }

// Paginated
{ "data": [ ... ],
  "meta": { "request_id": "...", "total": 123, "page": 1, "page_size": 50, "total_pages": 3 } }

// Error
{ "error": { "code": "RESOURCE_NOT_FOUND", "message": "..." } }
```

### Rate limits
200/min default; 30/min on auth and AI/chat endpoints; document upload/bulk endpoints 10/min; health
checks exempt. Exceeding a limit returns `429`.

---

## Health — `app/api/v1/health.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | none | Liveness. Returns status + version. Rate-limit exempt. |
| GET | `/health/ready` | none | Readiness. Checks DB, Azure AI Search, Azure OpenAI, Blob Storage; includes background-task failure counts. Cached 15s. |

## Users — `users.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/users/me` | user | Current user profile + active org memberships. |

## Organizations — `organizations.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/organizations` | platform admin | Create an organization. → 201 |
| GET | `/organizations` | user | List orgs the user belongs to. |
| GET | `/organizations/{org_id}` | user (member) | Org details. |
| PATCH | `/organizations/{org_id}` | ORG_ADMIN | Update name/status/settings. |
| POST | `/organizations/{org_id}/members` | ORG_ADMIN | Add member by user_id or email. → 201 |
| GET | `/organizations/{org_id}/members` | user (member) | List members. |
| PATCH | `/organizations/{org_id}/members/{user_id}` | ORG_ADMIN | Update a member's role. |
| DELETE | `/organizations/{org_id}/members/{user_id}` | ORG_ADMIN | Remove a member. → 204 |

## Risks — `risks.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/risks` | analyst+ | Create risk; evaluates threshold, may notify. → 201 |
| GET | `/risks` | member | List risks; filter by `status`, `risk_level`, `airport_identifier`; paginated. |
| GET | `/risks/{risk_id}` | member | Risk detail. |
| PATCH | `/risks/{risk_id}` | analyst+ | Update risk; re-evaluates threshold. |
| DELETE | `/risks/{risk_id}` | analyst+ | Delete risk + children. → 204 |
| POST | `/risks/{risk_id}/mitigations` | analyst+ | Create mitigation. → 201 |
| GET | `/risks/{risk_id}/mitigations` | member | List mitigations. |
| PATCH | `/risks/{risk_id}/mitigations/{mitigation_id}` | analyst+ | Update mitigation. |
| DELETE | `/risks/{risk_id}/mitigations/{mitigation_id}` | analyst+ | Delete mitigation. → 204 |

## Chat — `chat.py` (AI rate limit)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/chat` | analyst+ | Send a message; RAG + LLM; returns response + citations. → 201 |
| POST | `/chat/stream` | analyst+ | Stream the response as Server-Sent Events. |
| POST | `/chat/messages/email` | analyst+ | Email a chat response to a verified org member. → 202 |
| GET | `/chat/conversations` | member | List the user's conversations (paginated). |
| GET | `/chat/conversations/{conversation_id}` | member | Conversation + messages + citations. |
| DELETE | `/chat/conversations/{conversation_id}` | analyst+ | Delete a conversation. → 204 |

## Documents — `documents.py` (upload/bulk: 10/min)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/documents/upload` | analyst+ | Multipart upload (streamed); queues background processing. → 201 |
| GET | `/documents` | member | List documents (paginated). |
| GET | `/documents/{document_id}` | member | Document detail/status. |
| DELETE | `/documents/{document_id}` | analyst+ | Delete document + its search-index entries. → 204 |
| POST | `/documents/{document_id}/reindex` | analyst+ | Clear chunks and reprocess. |
| POST | `/documents/bulk-delete` | analyst+ | Batch delete by IDs. |
| GET | `/documents/stats/by-source` | analyst+ | Counts by source type. |
| POST | `/documents/process-all` | analyst+ | Queue all UPLOADED/FAILED/PROCESSING docs. |

## Notifications — `notifications.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/notifications` | user | List notifications; `unread_only` filter; paginated. |
| GET | `/notifications/unread-count` | user | Unread count. |
| PATCH | `/notifications/{notification_id}/read` | user | Mark one read. |
| POST | `/notifications/mark-all-read` | user | Mark all read. → 204 |
| GET | `/notifications/preferences/{token}` | token | Read email preference without login (10/min). |
| POST | `/notifications/preferences/{token}` | token | Update email opt-out without login (10/min). |

## Analytics — `analytics.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/analytics/dashboard` | user | Dashboard KPIs: risk counts, trends, mitigation performance. |
| GET | `/analytics/activity` | user | Recent activity entries (`limit` 1–50). |

## Audit — `audit.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/audit` | ORG_ADMIN | List audit entries; filter by action/resource/outcome/user/date; paginated. |
| GET | `/audit/filters` | ORG_ADMIN | Distinct filter values for the UI. |
| GET | `/audit/export` | ORG_ADMIN | CSV export (formula-injection-safe). Max 10,000 rows. |

## Search — `search.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/search` | member | Full-text search across conversations + documents. `q` (2–200 chars), `limit` 1–25. |

## Settings — `settings.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/settings` | user | All settings categories. |
| GET | `/settings/{category}` | user | One category (`rag`/`model`/`prompts`/`qaqc`). |
| PUT | `/settings/rag` | ORG_ADMIN | Update RAG settings. |
| PUT | `/settings/model` | ORG_ADMIN | Update model preferences. |
| PUT | `/settings/prompts` | ORG_ADMIN | Update system/function prompts. |
| PUT | `/settings/qaqc` | ORG_ADMIN | Update QA/QC reviewer settings. |

## SharePoint — `sharepoint.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/sharepoint/airports` | user | List airport folder names. |
| GET | `/sharepoint/risk-outcome-summary` | user | Aggregated risk-outcome summary (`refresh` to bust 5-min cache). |
| GET | `/sharepoint/drives` | analyst+ | List document libraries. |
| POST | `/sharepoint/crawl` | ORG_ADMIN | Discover + queue files for processing. |
| POST | `/sharepoint/sync-folder` | ORG_ADMIN | Re-download + reprocess a folder (path confined to the airport root). |

## Workflows — `workflows.py`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/workflows` | analyst+ | Create a PHL or SRA workflow. → 201 |
| GET | `/workflows` | analyst+ | List workflows; filter by `type`/`status`; paginated. |
| GET | `/workflows/{workflow_id}` | analyst+ | Workflow detail. |
| PATCH | `/workflows/{workflow_id}` | analyst+ | Update workflow data. |
| POST | `/workflows/{workflow_id}/submit` | analyst+ | DRAFT → SUBMITTED. |
| POST | `/workflows/{workflow_id}/approve` | ORG_ADMIN | SUBMITTED → APPROVED/REJECTED. |
| DELETE | `/workflows/{workflow_id}` | analyst+ | Delete workflow. → 204 |

## Risk-register sync — `rr_sync.py` (prefix `/rr`)
Dual-register sync between Faith Group and client orgs. Most endpoints are platform-admin only.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/rr/sync-queue` | member | List pending sync changes (filter by status). |
| POST | `/rr/sync-queue/{pending_id}/accept` | analyst+ | Accept a change; apply to counterpart org. |
| POST | `/rr/sync-queue/{pending_id}/reject` | analyst+ | Reject a change. |
| GET | `/rr/acp/{airport_identifier}` | platform admin | Get/create an Airport Context Profile. |
| PATCH | `/rr/acp/{acp_id}` | platform admin | Update an ACP. |
| POST | `/rr/acp/intelligence` | platform admin | Add an intelligence item. → 201 |
| GET | `/rr/acp/intelligence` | platform admin | List intelligence items. |
| POST | `/rr/acp/intelligence/{item_id}/decide` | platform admin | Decide on an item (accept/link/monitor/dismiss). |
| POST | `/rr/closures/{risk_id}/request` | analyst+ | Request closure approval for a High record. → 201 |
| POST | `/rr/closures/{approval_id}/decide` | analyst+ | Accountable Executive approves/rejects closure. |
| GET | `/rr/portfolio` | platform admin | Cross-org risk roll-up. |

---

For request/response field definitions, consult the Pydantic schemas in `backend/app/schemas/` (one
module per domain) — they are the source of truth and drive the generated OpenAPI document.
</content>
