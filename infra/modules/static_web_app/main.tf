resource "azurerm_static_web_app" "frontend" {
  name                = "swa-${var.name_prefix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  # M-19: Standard unlocks private endpoints, named environments, an SLA, and
  # the linked-backend mechanism used to take the Container App off the public
  # internet (H-11). ~$9/mo.
  sku_tier = "Standard"
  sku_size = "Standard"
  tags = merge(var.tags, {
    "azd-service-name" = "web"
  })
}
