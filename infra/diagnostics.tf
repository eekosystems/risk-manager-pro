# M-10: route platform logs and metrics from every resource to the central Log
# Analytics workspace. Required for the SOC 2 audit trail (CC7.2/CC7.3) — without
# these, control-plane and data-plane activity on these resources is not retained
# anywhere queryable.
#
# The Container App's platform logs are already shipped to the same workspace via
# the Container App Environment's log_analytics_workspace_id wiring
# (modules/container_app/main.tf), so it is intentionally not duplicated here.

locals {
  diagnostics_workspace_id = module.monitoring.log_analytics_workspace_id
}

resource "azurerm_monitor_diagnostic_setting" "key_vault" {
  name                       = "diag-${local.name_prefix}-kv"
  target_resource_id         = module.keyvault.vault_id
  log_analytics_workspace_id = local.diagnostics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

# Storage logs (blob reads/writes/deletes — including audit-log container access)
# live on the blob sub-resource, not the account, so target blobServices/default.
resource "azurerm_monitor_diagnostic_setting" "storage_blob" {
  name                       = "diag-${local.name_prefix}-blob"
  target_resource_id         = "${module.storage.storage_account_id}/blobServices/default"
  log_analytics_workspace_id = local.diagnostics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "postgres" {
  name                       = "diag-${local.name_prefix}-pg"
  target_resource_id         = module.database.server_id
  log_analytics_workspace_id = local.diagnostics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "container_registry" {
  name                       = "diag-${local.name_prefix}-acr"
  target_resource_id         = module.container_registry.id
  log_analytics_workspace_id = local.diagnostics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "openai" {
  name                       = "diag-${local.name_prefix}-openai"
  target_resource_id         = module.ai_services.openai_id
  log_analytics_workspace_id = local.diagnostics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "search" {
  name                       = "diag-${local.name_prefix}-search"
  target_resource_id         = module.ai_services.search_id
  log_analytics_workspace_id = local.diagnostics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "communication" {
  name                       = "diag-${local.name_prefix}-acs"
  target_resource_id         = module.communication.communication_service_id
  log_analytics_workspace_id = local.diagnostics_workspace_id

  enabled_log {
    category_group = "allLogs"
  }
}
