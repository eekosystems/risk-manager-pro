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
}

module "storage" {
  source = "./modules/storage"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  name_prefix         = local.name_prefix
  tags                = var.tags

  subnet_id = module.network.storage_subnet_id
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

  keyvault_uri                = module.keyvault.vault_uri
  database_url                = module.database.connection_string
  openai_endpoint             = module.ai_services.openai_endpoint
  search_endpoint             = module.ai_services.search_endpoint
  storage_account_name        = module.storage.storage_account_name
  azure_ad_tenant_id          = var.azure_ad_tenant_id
  azure_ad_client_id          = var.azure_ad_client_id
  log_analytics_workspace_id  = module.monitoring.log_analytics_workspace_id
  container_registry_server   = module.container_registry.login_server
  container_registry_id       = module.container_registry.id
  cors_origins                = "[\"https://${module.static_web_app.default_hostname}\"]"
}

# Grant Container App managed identity access to Key Vault (breaks circular dependency)
resource "azurerm_role_assignment" "container_app_keyvault" {
  scope                = module.keyvault.vault_id
  role_definition_name = "Key Vault Secrets User"
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
