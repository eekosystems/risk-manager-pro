resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.name_prefix}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id
  infrastructure_subnet_id   = var.subnet_id
  tags                       = var.tags
}

resource "azurerm_container_app" "backend" {
  name                         = "ca-${var.name_prefix}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type = "SystemAssigned"
  }

  template {
    min_replicas = 1
    max_replicas = 5

    container {
      name   = "api"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" # Placeholder
      cpu    = 1.0
      memory = "2Gi"

      env {
        name  = "APP_ENV"
        value = "production"
      }

      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.openai_endpoint
      }

      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = var.search_endpoint
      }

      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = var.storage_account_name
      }

      env {
        name  = "AZURE_AD_TENANT_ID"
        value = var.azure_ad_tenant_id
      }

      env {
        name  = "AZURE_AD_CLIENT_ID"
        value = var.azure_ad_client_id
      }

      liveness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000
      }

      readiness_probe {
        transport = "HTTP"
        path      = "/health/ready"
        port      = 8000
      }
    }
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}
