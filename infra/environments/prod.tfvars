environment       = "production"
location          = "eastus2"
project_name      = "rmpfg"
db_admin_username = "rmpadmin"

audit_retention_days = 365
# H-9: lock the WORM immutability policy for production. IRREVERSIBLE — once a
# prod apply lands this, the immutability policy cannot be shortened or deleted
# for the full retention window. This is free (a storage policy) and is the
# intended pre-audit posture; verify audit-log writes are healthy before the
# apply that locks it.
audit_immutability_locked = true

# H-12: cost-deferred. The General Purpose tier + zone-redundant HA +
# geo-redundant backup (~$250-300/mo) is the go-live posture, but it is held off
# until then to avoid paying for HA pre-production. These stay on the cheap
# Burstable tier for now. H-12 (availability/DR) remains OPEN until go-live, at
# which point flip to:
#   postgres_sku                   = "GP_Standard_D2s_v3"
#   postgres_ha_enabled            = true
#   postgres_geo_redundant_backup  = true
# Note: HA and geo-redundant backup both REQUIRE the GP tier — they cannot be
# enabled on Burstable, so all three move together.
postgres_sku                   = "B_Standard_B1ms"
postgres_ha_enabled            = false
postgres_geo_redundant_backup  = false
postgres_backup_retention_days = 35
