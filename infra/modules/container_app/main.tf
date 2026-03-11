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

  registry {
    server               = var.container_registry_server
    username             = var.container_registry_username
    password_secret_name = "registry-password"
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "api"
      image  = "${var.container_registry_server}/rmp-backend:latest"
      cpu    = 0.25
      memory = "0.5Gi"

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

      env {
        name  = "CORS_ORIGINS"
        value = "https://lemon-tree-0d582c90f.2.azurestaticapps.net"
      }

      liveness_probe {
        transport        = "HTTP"
        path             = "/api/v1/health"
        port             = 8000
        initial_delay    = 15
        interval_seconds = 30
      }

      readiness_probe {
        transport = "HTTP"
        path      = "/api/v1/health"
        port      = 8000
      }
    }
  }

  secret {
    name  = "database-url"
    value = var.database_url
  }

  secret {
    name  = "registry-password"
    value = var.container_registry_password
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
