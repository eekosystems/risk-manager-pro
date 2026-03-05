output "postgresql_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "connection_string" {
  value     = "postgresql+asyncpg://${var.admin_username}:${var.admin_password}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/riskmanagerpro?sslmode=require"
  sensitive = true
}

output "server_id" {
  value = azurerm_postgresql_flexible_server.main.id
}
