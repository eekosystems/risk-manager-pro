resource "azurerm_cognitive_account" "openai" {
  name                  = "oai-${var.name_prefix}"
  resource_group_name   = var.resource_group_name
  location              = var.location
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "oai-${var.name_prefix}"
  tags                  = var.tags

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = "Deny"

    virtual_network_rules {
      subnet_id = var.container_app_subnet_id
    }
  }
}

resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = "gpt-4o"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-08-06"
  }

  sku {
    name     = "Standard"
    capacity = 30
  }
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-3-small"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }

  sku {
    name     = "Standard"
    capacity = 120
  }
}

resource "azurerm_search_service" "main" {
  name                          = "search-${var.name_prefix}"
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = "basic"
  replica_count                 = 1
  partition_count               = 1
  public_network_access_enabled = false
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }
}
