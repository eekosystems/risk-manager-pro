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

variable "tenant_id" {
  type = string
}

# M-9: Key Vault firewall. Defaults are permissive ("Allow") so the deployer can
# write secrets (database-url, appinsights-connection-string) during apply and dev
# is unaffected. In production set default_action = "Deny" and supply either the
# deployer/runner egress IP in allowed_ip_rules or run Terraform from inside the
# VNet, and pair with a private endpoint — otherwise the secret writes fail.
variable "network_default_action" {
  description = "Key Vault firewall default action: 'Allow' (dev) or 'Deny' (prod)."
  type        = string
  default     = "Allow"
}

variable "allowed_subnet_ids" {
  description = "Subnets allowed through the KV firewall (must have the Microsoft.KeyVault service endpoint)."
  type        = list(string)
  default     = []
}

variable "allowed_ip_rules" {
  description = "Public IP/CIDR ranges allowed through the KV firewall (e.g. the deployer egress IP)."
  type        = list(string)
  default     = []
}
