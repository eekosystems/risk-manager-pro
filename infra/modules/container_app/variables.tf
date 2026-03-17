variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "subnet_id" {
  type = string
}

variable "keyvault_uri" {
  type = string
}

variable "database_url" {
  type      = string
  sensitive = true
}

variable "openai_endpoint" {
  type = string
}

variable "search_endpoint" {
  type = string
}

variable "storage_account_name" {
  type = string
}

variable "azure_ad_tenant_id" {
  type = string
}

variable "azure_ad_client_id" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "container_registry_server" {
  type = string
}

variable "container_registry_id" {
  type        = string
  description = "Resource ID of the ACR for AcrPull role assignment"
}

variable "cors_origins" {
  type        = string
  description = "JSON array of allowed CORS origins"
}
