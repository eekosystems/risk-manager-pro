output "openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "openai_id" {
  value = azurerm_cognitive_account.openai.id
}

output "search_endpoint" {
  value = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "search_id" {
  value = azurerm_search_service.main.id
}
