# Frontend Guide

The frontend is a **React 18 + TypeScript (strict)** single-page app built with **Vite**, styled with
**Tailwind CSS**, authenticated via **MSAL.js** (Entra ID), and using **TanStack Query** for server
state. It is hosted on **Azure Static Web Apps**.

For setup, see the [Local Development Runbook](../runbooks/local-dev.md). This guide explains the
structure and the conventions to follow.

## 1. Layout

```
frontend/src/
├── main.tsx           # Entry: MSAL init, QueryClient, provider stack
├── app.tsx            # Router: /login and protected /* → AppLayout → ChatPage
├── api/               # Typed API modules, one per domain (chat, risks, documents, …)
├── components/
│   ├── analytics/     # Dashboard + charts
│   ├── audit/         # Audit log viewer
│   ├── auth/          # LoginPage, ProtectedRoute, inactivity timeout
│   ├── chat/          # Chat page (primary screen)
│   ├── layout/        # App shell (sidebars, panels, view switching)
│   ├── notifications/ # Notification bell + list
│   ├── risk-register/ # Risk CRUD, portfolio, sync review
│   ├── search/        # Cmd+K search modal
│   ├── settings/      # Admin settings tabs
│   ├── ui/            # Reusable primitives
│   └── workflows/     # PHL / SRA wizards
├── config/            # MSAL + env config (auth.ts)
├── constants/         # Function definitions
├── context/           # React context (organization)
├── hooks/             # Data + UI hooks (TanStack Query wrappers)
├── lib/               # api-client (axios), logger, followups, exports
├── types/             # Centralized API TypeScript types
└── test/              # Vitest setup
```

## 2. Bootstrap & providers (`main.tsx`)

The provider stack, outermost first:

1. `MsalProvider` — Entra ID context (`PublicClientApplication`).
2. `QueryClientProvider` — TanStack Query (30s stale time; no retry on 401/403/429).
3. `BrowserRouter` — routing.
4. `ToastProvider` — toasts.
5. `OrganizationProvider` — active-tenant context.
6. `App`.

`app.tsx` routes `/login` (public) and everything else through `ProtectedRoute → AppLayout → ChatPage`,
all wrapped in a top-level `ErrorBoundary`.

## 3. Authentication (`config/auth.ts`, `hooks/use-auth.ts`)

- **Single-tenant enforced:** the authority must be tenant-specific; `/common`, `/organizations`, and
  `/consumers` authorities are rejected.
- **MSAL config:** token cache in `sessionStorage` (not persistent cookies); PII logging off in prod.
- **Login:** `loginRedirect` with `prompt: select_account`, scope `User.Read`.
- **API tokens:** acquired silently for the API scope (`VITE_API_SCOPE`, default
  `api://{clientId}/access_as_user`).
- **Protected routes:** show a spinner during the MSAL flow, redirect unauthenticated users to `/login`,
  and run an **inactivity timeout** that warns before logging the user out (matches the backend's 60-min
  idle session).

## 4. API client (`lib/api-client.ts`)

A single axios instance:

- **Base URL** from `VITE_API_BASE_URL`; 30s timeout.
- **Request interceptor:** acquires an access token via MSAL silent auth (with a 10s guard), sets
  `Authorization: Bearer …`, and adds `X-Organization-ID` when an org is active.
- **Response interceptor:** on `401`, clears only RMP app state from `sessionStorage` (preserving the
  MSAL cache) and redirects to `/login`.

The per-domain modules in `src/api/` (`chat.ts`, `risks.ts`, `documents.ts`, `organizations.ts`,
`analytics.ts`, `audit.ts`, `settings.ts`, `search.ts`, `users.ts`, `notifications.ts`, `workflows.ts`,
`health.ts`, `sharepoint.ts`, `rr-sync.ts`) wrap endpoints and return typed `DataResponse<T>` /
`PaginatedResponse<T>` shapes. **Never call `fetch`/`axios` inline in a component** — go through these
modules and a hook.

## 5. State management

- **Server state:** TanStack Query, wrapped in custom hooks in `src/hooks/` (`use-chat`, `use-risks`,
  `use-documents`, `use-organization`, `use-analytics`, `use-audit`, `use-search`, `use-notifications`,
  `use-workflow`). Query keys include the org ID so cache is isolated per tenant; mutations invalidate
  the relevant keys.
- **UI / tenant state:** React context. `OrganizationProvider` (`context/organization-context.tsx`)
  tracks the active org, persists it to `sessionStorage` (`rmp_active_org_id`), and pushes it into the
  axios interceptor. Layout state (current view, sidebars) persists to `localStorage` (`rmp:layout:v1`).

## 6. Key screens

| Screen | Component | Notes |
|--------|-----------|-------|
| **Chat** (primary) | `chat/chat-page.tsx` | Five function types; document upload with index polling; streaming responses; follow-up chips parsed from a `<followups>` block |
| **Risk register** | `risk-register/risk-register-page.tsx` | Risk list (search/filter), risk detail + edit, portfolio view (platform admin), sync review (feature-flagged off) |
| **Analytics** | `analytics/analytics-dashboard.tsx` | KPI cards, trend/donut/bar charts, risk matrix heatmap, activity feed (Recharts) |
| **Audit log** | `audit/audit-log-page.tsx` | Filterable table + CSV export (admin) |
| **Settings** | `settings/settings-page.tsx` | Indexed files, model, prompts, QAQC, users/roles (admin) |
| **Search** | `search/search-modal.tsx` | Cmd+K; debounced; conversations + documents |

**Chat upload flow:** files upload, then the page polls `GET /documents/{id}` (~1.5s interval, 90s
timeout) until `status = indexed` before sending the chat message — this avoids a RAG cache miss on
freshly uploaded content. Recent upload IDs are sent with the chat request so the backend can prioritize
them.

**Feature flags (in code):** `EMAIL_ON_CHAT_OUTPUT_ENABLED` (chat→email, currently off) and the
risk-register sync-review tab (currently off).

## 7. Build & tooling

| Script | Command | Purpose |
|--------|---------|---------|
| `dev` | `vite` | Dev server (port 5173, proxies `/api` → `localhost:8000`) |
| `build` | `tsc -b && vite build` | Type-check, then bundle to `dist/` |
| `lint` | `eslint src --max-warnings 0` | Zero-warning lint gate |
| `type-check` | `tsc --noEmit` | Types only |
| `test` / `test:watch` / `test:coverage` | `vitest …` | Unit tests (jsdom, Testing Library, MSW) |

**TypeScript is strict**, including `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`. ESLint
forbids explicit `any`. Path alias `@` → `src/`.

**Required env vars** (`frontend/.env.local`):
```
VITE_API_BASE_URL
VITE_AZURE_AD_CLIENT_ID
VITE_AZURE_AD_AUTHORITY
VITE_AZURE_AD_REDIRECT_URI
VITE_API_SCOPE
```
At deploy time these are injected by the pipeline / `azure.yaml` from the provisioned resources.

## 8. Conventions

- Functional components only; explicit props interfaces.
- `kebab-case.tsx` for components, `use-kebab-case.ts` for hooks.
- Logic lives in hooks; components stay mostly JSX.
- Markdown responses are rendered with `react-markdown` + `rehype-sanitize`. Never use
  `dangerouslySetInnerHTML`.
- Keep user-facing strings i18n-ready (avoid hardcoding in JSX where practical).
</content>
