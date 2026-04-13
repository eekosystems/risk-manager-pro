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

variable "subnet_id" {
  type = string
}

variable "audit_retention_days" {
  description = "Immutability retention period in days for audit logs (~7 years default)"
  type        = number
  default     = 2555
}

variable "audit_immutability_locked" {
  description = "Whether to lock the audit container immutability policy. IRREVERSIBLE: once locked, the policy cannot be shortened or deleted for the full retention_days period. Flip to true only after a burn-in window in production."
  type        = bool
  default     = false
}
