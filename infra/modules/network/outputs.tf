output "vnet_id" {
  value = azurerm_virtual_network.main.id
}

output "database_subnet_id" {
  value = azurerm_subnet.database.id
}

output "container_app_subnet_id" {
  value = azurerm_subnet.container_app.id
}

output "storage_subnet_id" {
  value = azurerm_subnet.storage.id
}

output "postgres_private_dns_zone_id" {
  value = azurerm_private_dns_zone.postgres.id
}
