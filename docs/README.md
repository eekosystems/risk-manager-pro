# Risk Manager Pro — Developer Documentation

This is the engineering handoff documentation for **Risk Manager Pro (RMP)**, an AI-driven
operational risk-management platform for private aviation safety, built for Faith Group LLC and
deployed to Azure.

If you are new to the project, read the docs in this order:

1. **[Architecture Overview](architecture/overview.md)** — what the system is and how the pieces fit together.
2. **[New Engineer Onboarding](onboarding/new-engineer.md)** — get a working local environment and make your first change.
3. **[Local Development Runbook](runbooks/local-dev.md)** — day-to-day commands (DB, backend, frontend, tests, migrations).

## Documentation map

| Area | Document | Read it when you need to… |
|------|----------|----------------------------|
| **Architecture** | [overview.md](architecture/overview.md) | Understand components, request flow, and tech stack |
| | [data-model.md](architecture/data-model.md) | Understand the database schema and entity relationships |
| | [rag-pipeline.md](architecture/rag-pipeline.md) | Understand document ingestion and AI retrieval/answering |
| **Backend** | [backend-guide.md](backend/backend-guide.md) | Work on the FastAPI backend (layers, services, config) |
| **Frontend** | [frontend-guide.md](frontend/frontend-guide.md) | Work on the React frontend (routing, auth, state, features) |
| **API** | [api-reference.md](api/api-reference.md) | Look up an endpoint, its auth, and its request/response shape |
| **Deployment** | [deployment-runbook.md](deployment/deployment-runbook.md) | Deploy to Azure or change the CI/CD pipelines |
| | [infrastructure.md](deployment/infrastructure.md) | Understand the Terraform IaC and Azure topology |
| **Operations** | [operations-runbook.md](operations/operations-runbook.md) | Monitor, troubleshoot, roll back, or respond to an incident |
| | [security-compliance.md](operations/security-compliance.md) | Understand auth, RBAC, audit logging, and SOC 2 controls |
| **Reference** | [glossary.md](reference/glossary.md) | Decode aviation-safety and domain terminology |
| **Standards** | [../ENGINEERING_STANDARDS.md](../ENGINEERING_STANDARDS.md) | Follow the mandatory coding and compliance standards |

## What this product is, in one paragraph

RMP is a multi-tenant SaaS platform. Aviation safety analysts interact primarily through a
**chat interface** backed by a Retrieval-Augmented Generation (RAG) pipeline over aviation safety
documentation (FAA, ICAO, EASA, NASA ASRS, and client documents). The platform supports the core
Safety Management System (SMS) workflows — hazard identification (PHL), Safety Risk Assessment (SRA),
risk-register entry, mitigation tracking, and safety analytics — and maintains a dual risk register
that synchronizes between Faith Group and its airport clients. Every state-changing action is audit
logged for SOC 2 compliance.

## Tech stack at a glance

- **Frontend:** React 18 + TypeScript (strict) + Vite + Tailwind, MSAL.js for Entra ID auth, TanStack Query. Hosted on Azure Static Web Apps.
- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + Alembic. Hosted on Azure Container Apps.
- **Data:** Azure Database for PostgreSQL (Flexible Server, pgvector), Azure AI Search (hybrid keyword + vector), Azure Blob Storage.
- **AI:** Azure OpenAI (GPT-4o chat + vision, text-embedding-3-small).
- **Platform:** Entra ID (auth), Key Vault + Managed Identity (secrets), Azure Communication Services (email), Azure Monitor + Application Insights (observability).
- **IaC / CI-CD:** Terraform + Azure DevOps Pipelines (`azure-pipelines.yml`, canonical CI/CD).

> **Status note:** This documentation reflects the codebase as of the handoff. The platform completed
> a security audit (see [security-compliance.md](operations/security-compliance.md)); remediation is
> tracked there. High-availability database settings are intentionally cost-deferred until go-live —
> see [infrastructure.md](deployment/infrastructure.md).
</content>
</invoke>
