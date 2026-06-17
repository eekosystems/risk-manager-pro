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

  # DATABASE_URL is sourced from Key Vault via the system-assigned identity
  # rather than embedded as a plaintext env value (C-1). The MI is granted
  # "Key Vault Secrets User" in the root module.
  # Note: on a from-scratch apply the KV role assignment is created after this
  # resource, so the very first create may require a second apply (or a
  # pre-existing identity). The deployed environment already has the grant.
  secret {
    name                = "database-url"
    key_vault_secret_id = var.database_url_secret_id
    identity            = "System"
  }

  # M-12: the App Insights connection string carries the instrumentation key.
  # Source it from Key Vault via the managed identity rather than embedding it as
  # a plaintext env value where any "list container apps" reader could harvest it
  # and submit forged telemetry into Faith Group's APM stream.
  secret {
    name                = "appinsights-connection-string"
    key_vault_secret_id = var.appinsights_connection_string_secret_id
    identity            = "System"
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name  = "api"
      image = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      # Sized for large-file ingestion: streaming upload keeps peak memory low,
      # but text extraction of multi-GB documents still needs headroom.
      # Container Apps requires memory = 2 × cpu (Gi).
      cpu    = 2.0
      memory = "4Gi"

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
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
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
