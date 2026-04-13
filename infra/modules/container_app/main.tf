resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.name_prefix}"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_workspace_id
  infrastructure_subnet_id   = var.subnet_id
  tags                       = var.tags

  lifecycle {
    ignore_changes = [
      infrastructure_resource_group_name,
    ]
  }
}

resource "azurerm_container_app" "backend" {
  name                         = "ca-${var.name_prefix}-api"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"

  tags = merge(var.tags, {
    "azd-service-name" = "api"
  })

  identity {
    type = "SystemAssigned"
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "api"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "DATABASE_URL"
        value = var.database_url
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
        name  = "AZURE_SEARCH_INDEX_NAME"
        value = "rmp-documents"
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
        value = var.cors_origins
      }
      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        name  = "ACS_ENDPOINT"
        value = var.acs_endpoint
      }
      env {
        name  = "ACS_SENDER_ADDRESS"
        value = var.acs_sender_address
      }
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = var.applicationinsights_connection_string
      }
      env {
        name  = "OTEL_SERVICE_NAME"
        value = "risk-manager-pro-api"
      }
    }
  }

  ingress {
    external_enabled           = true
    target_port                = 8000
    transport                  = "http"
    allow_insecure_connections = false

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

# Grant Container App system-assigned identity AcrPull on the registry
resource "azurerm_role_assignment" "container_app_acr_pull" {
  scope                = var.container_registry_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.backend.identity[0].principal_id
}
