output "app_url" {
  value = "https://${azurerm_container_app.backend.ingress[0].fqdn}"
}

output "identity_principal_id" {
  value = azurerm_container_app.backend.identity[0].principal_id
}
