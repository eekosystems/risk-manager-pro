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
  default     = "rmp"
}

variable "azure_ad_tenant_id" {
  description = "Azure AD tenant ID for authentication"
  type        = string
  sensitive   = true
}

variable "azure_ad_client_id" {
  description = "Azure AD application (client) ID"
  type        = string
  sensitive   = true
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
