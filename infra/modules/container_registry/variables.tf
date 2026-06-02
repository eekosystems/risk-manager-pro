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
  type    = map(string)
  default = {}
}

# M-13: ACR SKU. Basic keeps cost at ~$5/mo and supports the credential hardening
# (no admin, no anonymous pull). Premium (~$50/mo) is required for network rules,
# private endpoints, quarantine, and geo-replication — set it only when ready to
# pay for and operate those.
variable "acr_sku" {
  type    = string
  default = "Basic"
}

# M-13: keep public network access on by default so the CI build agents can
# `az acr login` and push over the internet. Set false in production only once
# pushes run from inside the VNet (self-hosted agent or ACR Tasks) reaching the
# registry through a private endpoint — otherwise the image push breaks.
variable "public_network_access_enabled" {
  type    = bool
  default = true
}

# M-13: image quarantine holds every freshly pushed image until a scanner marks
# it trusted. Default off because the deploy pipeline pulls the image immediately
# after push — enabling it without a scanner (e.g. Defender for Containers) to
# release images would break the pull. Turn on once that scanner is wired in.
variable "quarantine_policy_enabled" {
  type    = bool
  default = false
}
