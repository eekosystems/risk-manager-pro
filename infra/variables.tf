variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus2"
}

variable "project_name" {
  description = "Project name used in resource naming"
  type        = string
  default     = "rmpfg"
}

variable "azure_ad_tenant_id" {
  description = "Azure AD tenant ID for authentication"
  type        = string
  sensitive   = true
  default     = ""
}

variable "azure_ad_client_id" {
  description = "Azure AD application (client) ID"
  type        = string
  sensitive   = true
  default     = ""
}

variable "db_admin_username" {
  description = "PostgreSQL administrator username"
  type        = string
  default     = "rmpadmin"
}

variable "db_admin_password" {
  description = "PostgreSQL administrator password"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Common tags applied to all resources"
  type        = map(string)
  default = {
    project    = "risk-manager-pro"
    managed_by = "terraform"
    client     = "faith-group"
    compliance = "soc2"
  }
}

variable "audit_retention_days" {
  description = "Immutability retention period in days for audit logs (SOC 2 CC7.2)"
  type        = number
  default     = 365
}

variable "audit_immutability_locked" {
  description = "Lock the audit immutability policy. IRREVERSIBLE — only flip to true in prod after burn-in"
  type        = bool
  default     = false
}

variable "postgres_ha_enabled" {
  description = "Enable zone-redundant HA on Postgres flexible server (requires GP or MO tier)"
  type        = bool
  default     = false
}

variable "postgres_backup_retention_days" {
  description = "Postgres backup retention days (7-35)"
  type        = number
  default     = 35
}

variable "postgres_geo_redundant_backup" {
  description = "Enable geo-redundant Postgres backups"
  type        = bool
  default     = true
}
