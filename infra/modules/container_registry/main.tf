resource "azurerm_container_registry" "main" {
  name                = replace("acr${var.name_prefix}", "-", "")
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}
