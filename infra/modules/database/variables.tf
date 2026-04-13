variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "admin_username" {
  type = string
}

variable "admin_password" {
  type      = string
  sensitive = true
}

variable "subnet_id" {
  type = string
}

variable "private_dns_zone_id" {
  type = string
}

variable "backup_retention_days" {
  description = "Number of days to retain backups (7-35)"
  type        = number
  default     = 35
}

variable "geo_redundant_backup_enabled" {
  description = "Whether to enable geo-redundant backups (requires non-B-tier SKU)"
  type        = bool
  default     = false
}

variable "ha_enabled" {
  description = "Enable ZoneRedundant high availability (requires GP or MO tier)"
  type        = bool
  default     = false
}

variable "sku_name" {
  description = "Flexible server SKU. B_Standard_B1ms for dev; GP_Standard_D2s_v3 or higher for HA/geo-backup"
  type        = string
  default     = "B_Standard_B1ms"
}

variable "standby_availability_zone" {
  description = "Availability zone for the HA standby replica"
  type        = string
  default     = "2"
}
