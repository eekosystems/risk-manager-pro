# Glossary

Domain and technical terms used across Risk Manager Pro. Aviation safety terminology must be used
correctly — these definitions are the reference.

## Aviation safety (SMS) terms

| Term | Meaning |
|------|---------|
| **SMS** | Safety Management System — the organization-wide framework for managing safety risk. |
| **SRM** | Safety Risk Management — the SMS process of identifying hazards and assessing/controlling their risk. |
| **PHL** | Preliminary Hazard List — an initial enumeration of hazards in a system or operation. |
| **SRA** | Safety Risk Assessment — evaluation of a hazard's risk via severity × likelihood. |
| **Hazard** | A condition that could foreseeably cause or contribute to an aircraft accident or incident. |
| **Risk** | The composite of the predicted severity and likelihood of a hazard's potential outcome. |
| **Severity** | Consequence magnitude of a hazard's outcome. Modeled here as **1–5** (Minimal → Catastrophic). |
| **Likelihood** | Probability of the outcome. Modeled here as **A–E** (Frequent → Extremely Improbable). |
| **Risk matrix** | The 5×5 severity/likelihood grid (per FAA SMS guidance) that maps to a risk level. |
| **Risk level** | The matrix result: **LOW**, **MEDIUM**, or **HIGH**. |
| **Mitigation** | A control/action that reduces a hazard's severity or likelihood (its residual risk). |
| **Residual risk** | The risk remaining after existing controls/mitigations are applied. |
| **Risk register** | The system of record of identified risks for an airport/organization. |
| **ACP** | Airport Context Profile — per-airport intelligence (system profile, known risk factors, stakeholder notes, history) maintained at the platform level. |
| **Accountable Executive** | The individual accountable for the SMS; here, the approver for High-risk closures. |
| **Operational domain** | Where a hazard applies: movement area, non-movement area, ramp, terminal, landside, or user-defined. |
| **5M model** | Hazard categorization: Human, Machine, Medium, Mission, Management. |
| **ICAO hazard categories** | Technical, Human, Organizational, Environmental. |

## Regulatory references

| Term | Meaning |
|------|---------|
| **FAA** | Federal Aviation Administration (US civil aviation regulator). |
| **FAR** | Federal Aviation Regulations (14 CFR). |
| **ICAO** | International Civil Aviation Organization. |
| **ICAO Annex 19** | The ICAO annex on Safety Management. |
| **EASA** | European Union Aviation Safety Agency. |
| **NASA ASRS** | NASA Aviation Safety Reporting System — voluntary safety report database; a document source type. |
| **NOTAM** | Notice to Air Missions — operational notices; an intelligence-item source. |

## Product / function terms

| Term | Meaning |
|------|---------|
| **Function type** | The mode a chat turn operates in: `general`, `phl`, `sra`, `system`, `risk_register`. |
| **Smart routing** | Automatic selection of the function type for an incoming chat message (`CHAT_SMART_ROUTING`). |
| **Dual risk register** | The Faith Group ↔ client synchronization model: paired records, a pending-change review queue, and a closure-approval gate. |
| **Sync change** | A proposed create/update/close flowing between paired registers, reviewed before it applies. |
| **Citation** | A source reference attached to an AI answer, linking back to an indexed document chunk. |
| **QA/QC digest** | The daily quality-assurance email summarizing items for reviewer attention. |

## Technical / platform terms

| Term | Meaning |
|------|---------|
| **RAG** | Retrieval-Augmented Generation — retrieve relevant document chunks, then have the LLM answer grounded in them. See [rag-pipeline.md](../architecture/rag-pipeline.md). |
| **Tenant / organization** | A client account; the unit of data isolation (`organization_id` / `tenant_id`). |
| **RBAC** | Role-Based Access Control — VIEWER / ANALYST / ORG_ADMIN, plus platform admin. |
| **Platform admin** | A Faith Group super-user with cross-organization visibility. |
| **Entra ID** | Microsoft Entra ID (formerly Azure AD) — the identity provider. |
| **MSAL** | Microsoft Authentication Library — the frontend's Entra ID auth client. |
| **Managed Identity** | An Azure identity for the app to access other Azure services without stored credentials. |
| **Key Vault** | Azure secret store; secrets are referenced, never embedded in code. |
| **Correlation ID** | A per-request UUID threaded through logs, audit entries, and responses for tracing. |
| **WORM** | Write Once, Read Many — the immutability model applied to the audit-log blob container. |
| **Hybrid search** | Combined keyword + vector search (Azure AI Search) used by the RAG retrieval step. |
| **pgvector** | PostgreSQL extension for vector storage (the documented fallback to Azure AI Search). |
| **azd** | Azure Developer CLI — orchestrates provisioning + deploy via `azure.yaml`. |
| **ACS** | Azure Communication Services — the email delivery service. |
</content>
