environment       = "production"
location          = "eastus2"
project_name      = "rmpfg"
db_admin_username = "rmpadmin"

audit_retention_days      = 365
# IRREVERSIBLE: set to true only after burn-in validation. Once locked,
# the immutability policy cannot be shortened or deleted for the full
# retention window.
audit_immutability_locked = false

# Requires SKU bump — set sku_name via -var when flipping ha_enabled=true
postgres_ha_enabled            = false
postgres_geo_redundant_backup  = true
postgres_backup_retention_days = 35
