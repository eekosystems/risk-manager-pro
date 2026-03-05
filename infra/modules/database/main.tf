resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "psql-${var.name_prefix}"
  resource_group_name           = var.resource_group_name
  location                      = var.location
  version                       = "16"
  delegated_subnet_id           = var.subnet_id
  private_dns_zone_id           = var.private_dns_zone_id
  administrator_login           = var.admin_username
  administrator_password        = var.admin_password
  storage_mb                    = 32768
  sku_name                      = "GP_Standard_D2s_v3"
  zone                          = "1"
  public_network_access_enabled = false
  tags                          = var.tags

  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = true
  }
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = "riskmanagerpro"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "vector"
}
