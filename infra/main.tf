locals {
  # Sanitize: replace underscores with hyphens so Azure resource names stay valid
  name_prefix = replace("${var.project_name}-${var.environment}", "_", "-")
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = var.tags
}

module "network" {
  source = "./modules/network"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags
}

module "database" {
  source = "./modules/database"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags

  admin_username      = var.db_admin_username
  admin_password      = var.db_admin_password
  subnet_id           = module.network.database_subnet_id
  private_dns_zone_id = module.network.postgres_private_dns_zone_id

  backup_retention_days        = var.postgres_backup_retention_days
  geo_redundant_backup_enabled = var.postgres_geo_redundant_backup
  ha_enabled                   = var.postgres_ha_enabled
}

module "storage" {
  source = "./modules/storage"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags

  subnet_id                 = module.network.storage_subnet_id
  audit_retention_days      = var.audit_retention_days
  audit_immutability_locked = var.audit_immutability_locked
}

module "ai_services" {
  source = "./modules/ai_services"

  resource_group_name     = azurerm_resource_group.main.name
  location                = var.location
  name_prefix             = local.name_prefix
  tags                    = var.tags
  container_app_subnet_id = module.network.container_app_subnet_id
  search_location         = "eastus"
}

module "keyvault" {
  source = "./modules/keyvault"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags

  tenant_id = var.azure_ad_tenant_id
}

module "communication" {
  source = "./modules/communication"

  resource_group_name = azurerm_resource_group.main.name
  name_prefix         = local.name_prefix
  tags                = var.tags
}

module "container_registry" {
  source = "./modules/container_registry"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags
}

module "container_app" {
  source = "./modules/container_app"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags

  subnet_id = module.network.container_app_subnet_id

  keyvault_uri               = module.keyvault.vault_uri
  database_url               = module.database.connection_string
  openai_endpoint            = module.ai_services.openai_endpoint
  search_endpoint            = module.ai_services.search_endpoint
  storage_account_name       = module.storage.storage_account_name
  azure_ad_tenant_id         = var.azure_ad_tenant_id
  azure_ad_client_id         = var.azure_ad_client_id
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  container_registry_server  = module.container_registry.login_server
  container_registry_id      = module.container_registry.id
  cors_origins               = "[\"https://${module.static_web_app.default_hostname}\"]"

  acs_endpoint       = module.communication.communication_service_endpoint
  acs_sender_address = module.communication.email_sender_address

  applicationinsights_connection_string = module.monitoring.app_insights_connection_string
}

# Grant Container App managed identity access to Key Vault
resource "azurerm_role_assignment" "container_app_keyvault" {
  scope                = module.keyvault.vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = module.container_app.identity_principal_id
}

# Grant Container App managed identity access to Azure OpenAI
resource "azurerm_role_assignment" "container_app_openai" {
  scope                = module.ai_services.openai_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = module.container_app.identity_principal_id
}

# Grant Container App managed identity access to Azure AI Search
resource "azurerm_role_assignment" "container_app_search" {
  scope                = module.ai_services.search_id
  role_definition_name = "Search Index Data Reader"
  principal_id         = module.container_app.identity_principal_id
}

# Grant Container App managed identity access to Azure Blob Storage
resource "azurerm_role_assignment" "container_app_storage" {
  scope                = module.storage.storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = module.container_app.identity_principal_id
}

# Grant Container App managed identity access to Azure Communication Services
# for sending QA/QC notification emails via EmailClient (no API keys required).
resource "azurerm_role_assignment" "container_app_communication" {
  scope                = module.communication.communication_service_id
  role_definition_name = "Contributor"
  principal_id         = module.container_app.identity_principal_id
}

module "static_web_app" {
  source = "./modules/static_web_app"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags
}

module "monitoring" {
  source = "./modules/monitoring"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags
}
