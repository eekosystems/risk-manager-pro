output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "postgresql_fqdn" {
  value     = module.database.postgresql_fqdn
  sensitive = true
}

output "storage_account_name" {
  value = module.storage.storage_account_name
}

output "openai_endpoint" {
  value     = module.ai_services.openai_endpoint
  sensitive = true
}

output "search_endpoint" {
  value = module.ai_services.search_endpoint
}

output "container_app_url" {
  value = module.container_app.app_url
}

output "static_web_app_url" {
  value = module.static_web_app.default_hostname
}

output "keyvault_uri" {
  value = module.keyvault.vault_uri
}

output "container_registry_login_server" {
  value = module.container_registry.login_server
}

output "container_registry_name" {
  value = module.container_registry.name
}

output "static_web_app_api_key" {
  value     = module.static_web_app.api_key
  sensitive = true
}

# -------------------------------------------------------------------
# Azure Developer CLI (azd) outputs
# azd reads these to know where to deploy each service.
# -------------------------------------------------------------------

output "AZURE_CONTAINER_REGISTRY_ENDPOINT" {
  value = module.container_registry.login_server
}

output "AZURE_CONTAINER_REGISTRY_NAME" {
  value = module.container_registry.name
}

output "AZURE_RESOURCE_GROUP" {
  value = azurerm_resource_group.main.name
}

# Backend (Container App)
output "SERVICE_API_NAME" {
  value = "ca-${local.name_prefix}-api"
}

output "SERVICE_API_RESOURCE_GROUP" {
  value = azurerm_resource_group.main.name
}

output "SERVICE_API_URI" {
  value = module.container_app.app_url
}

# Frontend (Static Web App)
output "SERVICE_WEB_URI" {
  value = module.static_web_app.default_hostname
}

output "SERVICE_WEB_RESOURCE_GROUP" {
  value = azurerm_resource_group.main.name
}

output "SERVICE_WEB_NAME" {
  value = "swa-${local.name_prefix}"
}
