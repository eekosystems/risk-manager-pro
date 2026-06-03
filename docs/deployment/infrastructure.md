# Infrastructure

All Azure infrastructure is defined as code with **Terraform** in `infra/`. Nothing is created by hand
in the Azure portal — portal changes drift from state and violate the change-management control (CC8.1).

## 1. Layout

```
infra/
├── main.tf            # Orchestrates the modules; resource group; tags
├── providers.tf       # azurerm ~> 4.0; Terraform >= 1.5.0
├── backend.tf         # Remote state (Azure Storage)
├── variables.tf       # Root inputs
├── outputs.tf         # Root outputs (+ azd integration outputs)
├── diagnostics.tf     # Diagnostic settings → Log Analytics for every resource
├── environments/
│   ├── dev.tfvars
│   └── prod.tfvars
└── modules/
    ├── network/           ├── database/         ├── storage/
    ├── ai_services/       ├── keyvault/         ├── communication/
    ├── container_registry/├── container_app/    ├── static_web_app/
    └── monitoring/
```

**Remote state:** `azurerm` backend — storage account `rmpfgllctfstate`, resource group
`rmp-terraform-state`, container `tfstate`, key `riskmanagerpro.terraform.tfstate`.

**Naming:** resources are named `{type}-{project}-{environment}` with `project_name = "rmpfg"` (Risk
Manager Pro / Faith Group). The resource group is `rg-rmpfg-{environment}`. Default region `eastus2`.

**Common tags:** `project=risk-manager-pro`, `managed_by=terraform`, `client=faith-group`,
`compliance=soc2`.

## 2. Modules

| Module | Provisions | Notes |
|--------|-----------|-------|
| **network** | VNet `10.0.0.0/16` + 3 delegated subnets; private DNS for Postgres; NSG | DB subnet (`10.0.1.0/24`), container-app subnet (`10.0.2.0/23`), storage subnet (`10.0.4.0/24`). NSG allows 5432 only from the container-app subnet. |
| **database** | PostgreSQL Flexible Server 16 + pgvector; database `riskmanagerpro` | Private (no public access), TLS required, Entra ID + password auth. Backup retention + optional geo-redundancy/HA via variables. |
| **storage** | Storage account; `documents` + `audit-logs` containers | GRS, TLS 1.2+, public access off, shared-key off (OAuth only), blob versioning + 30-day soft delete. `audit-logs` has a WORM immutability policy. |
| **ai_services** | Azure OpenAI (`gpt-4o`, `text-embedding-3-small`) + Azure AI Search (Basic) | Managed identity, deny-by-default network ACLs, custom subdomain. Search index `rmp-documents`. |
| **keyvault** | Key Vault (RBAC mode, purge protection) | Stores `database-url` and `appinsights-connection-string`. Network firewall configurable (allow in dev, deny+allowlist in prod). |
| **communication** | Email Communication Service + Communication Service | Azure-managed email domain; least-privilege send-only role for the API identity. |
| **container_registry** | Azure Container Registry (Basic) | Admin auth off, anonymous pull off; API identity has `AcrPull`. |
| **container_app** | Container App Environment + the API Container App | System-assigned identity; 1–2 replicas, 0.5 vCPU / 1 GiB each; external HTTPS ingress on port 8000. Secrets pulled from Key Vault. |
| **static_web_app** | Azure Static Web App (Standard) | Hosts the frontend `dist/`; can link the Container App as a private backend. |
| **monitoring** | Log Analytics workspace + Application Insights + action group + error-rate metric alert | 90-day retention; alert fires on >10 failed requests in 15 min (severity 1). |

`diagnostics.tf` routes all logs/metrics from Key Vault, Storage, PostgreSQL, ACR, OpenAI, AI Search,
and Communication Services into the central Log Analytics workspace — the backbone of the SOC 2 audit
trail (CC7.2/CC7.3).

## 3. Identity & access (Managed Identity → RBAC)

The Container App's **system-assigned managed identity** is granted least-privilege roles — there are
**no stored credentials**:

| Target | Role |
|--------|------|
| Key Vault | Key Vault Secrets User |
| Azure OpenAI | Cognitive Services OpenAI User |
| Azure AI Search | Search Index Data Contributor |
| Blob Storage | Storage Blob Data Contributor |
| Communication Services | Custom **ACS Send Email** (send-only) |
| Container Registry | AcrPull |
| PostgreSQL | Configured as an Entra ID administrator (principal `rmp-api`) |

Secrets reach the app as Container App secret references (`secretref:database-url`,
`secretref:appinsights-connection-string`) sourced from Key Vault — not as plaintext environment values.

## 4. Network topology

```
Internet
   │ HTTPS
   ├──────────────▶ Static Web App (frontend)
   │
   └──────────────▶ Container App ingress (API, port 8000)
                         │  (system-assigned MI)
        VNet 10.0.0.0/16 │
   ┌─────────────────────┼──────────────────────────────┐
   │ snet-container-app  │  snet-database   snet-storage │
   │  10.0.2.0/23        │   10.0.1.0/24     10.0.4.0/24 │
   │      │              │       │               │       │
   │      ▼              ▼       ▼               ▼       │
   │  (CogServices SE)  Postgres(private)   Storage(SE)  │
   └─────────────────────────────────────────────────────┘
   Private DNS: privatelink.postgres.database.azure.com
   NSG: allow 5432 from container-app subnet → database subnet only
```

## 5. Environments

`infra/environments/dev.tfvars` vs `prod.tfvars`:

| Setting | dev | prod |
|---------|-----|------|
| `environment` | `dev` | `production` |
| `audit_immutability_locked` | `false` | `true` (WORM lock enabled post-burn-in) |
| `postgres_backup_retention_days` | `7` | `35` |
| `postgres_geo_redundant_backup` | `false` | `false` *(cost-deferred)* |
| `postgres_ha_enabled` | `false` | `false` *(cost-deferred)* |
| `postgres_sku` | `B_Standard_B1ms` | `B_Standard_B1ms` *(cost-deferred)* |
| `location`, `project_name`, `db_admin_username` | `eastus2` / `rmpfg` / `rmpadmin` | same |

> **Go-live action (tracked):** zone-redundant HA, a General-Purpose Postgres SKU
> (`GP_Standard_D2s_v3+`), and geo-redundant backups are intentionally deferred in `prod.tfvars` to
> control cost during pre-production. Flip these before production go-live. Once
> `audit_immutability_locked = true` is applied, the WORM lock on audit logs is **irreversible**.

## 6. Sensitive inputs

- `db_admin_password` — marked `sensitive`; injected at apply time from Key Vault / pipeline secret, never
  committed.
- `azure_ad_tenant_id` / `azure_ad_client_id` — not sensitive (they appear in issued JWTs) but are still
  passed as variables.

See [deployment-runbook.md](deployment-runbook.md) for how the pipelines invoke Terraform and supply
these values.
</content>
