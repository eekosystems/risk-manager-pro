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
