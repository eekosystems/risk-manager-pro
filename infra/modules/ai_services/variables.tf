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

variable "search_location" {
  type        = string
  description = "Location for Azure AI Search (override when primary region is at capacity)"
  default     = ""
}

variable "container_app_subnet_id" {
  type        = string
  description = "Subnet ID for the container app — used in network ACLs"
}
