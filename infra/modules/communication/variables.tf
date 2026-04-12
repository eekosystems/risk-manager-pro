variable "resource_group_name" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "tags" {
  type = map(string)
}

variable "data_location" {
  type        = string
  description = "Data residency for Communication Services (e.g., United States, Europe)"
  default     = "United States"
}
