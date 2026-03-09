resource "azurerm_storage_account" "main" {
  name                          = replace("st${var.name_prefix}fg", "-", "")
  resource_group_name           = var.resource_group_name
  location                      = var.location
  account_tier                  = "Standard"
  account_replication_type      = "GRS"
  min_tls_version               = "TLS1_2"
  public_network_access_enabled = false
  tags                          = var.tags

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 30
    }
  }
}

resource "azurerm_storage_container" "documents" {
  name                  = "documents"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "audit_logs" {
  name                  = "audit-logs"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "audit_immutability" {
  storage_account_id = azurerm_storage_account.main.id

  rule {
    name    = "audit-log-retention"
    enabled = true

    filters {
      prefix_match = ["audit-logs/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than = 30
        delete_after_days_since_modification_greater_than       = 2555 # ~7 years
      }
    }
  }
}

resource "azurerm_storage_container_immutability_policy" "audit_logs" {
  storage_container_resource_manager_id = azurerm_storage_container.audit_logs.resource_manager_id
  immutability_period_in_days           = var.audit_retention_days
  locked                                = false # Unlock during testing; lock in production
}

resource "azurerm_storage_account_network_rules" "main" {
  storage_account_id         = azurerm_storage_account.main.id
  default_action             = "Deny"
  bypass                     = ["AzureServices"]
  virtual_network_subnet_ids = [var.subnet_id]
}
