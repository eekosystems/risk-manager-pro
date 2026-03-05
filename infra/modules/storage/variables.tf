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
