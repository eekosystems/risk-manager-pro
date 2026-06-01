environment       = "production"
location          = "eastus2"
project_name      = "rmpfg"
db_admin_username = "rmpadmin"

audit_retention_days = 365
# H-9: lock the WORM immutability policy for production. IRREVERSIBLE — once a
# prod apply lands this, the immutability policy cannot be shortened or deleted
# for the full retention window. This is the intended pre-audit posture; verify
# audit-log writes are healthy before the apply that locks it.
audit_immutability_locked = true

# H-12: GP tier is required for zone-redundant HA and geo-redundant backups.
# Burstable (B-tier) supports neither, and geo_redundant_backup=true on a B SKU
# fails the apply outright.
postgres_sku                   = "GP_Standard_D2s_v3"
postgres_ha_enabled            = true
postgres_geo_redundant_backup  = true
postgres_backup_retention_days = 35
