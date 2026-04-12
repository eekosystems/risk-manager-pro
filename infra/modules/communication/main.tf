# Azure Communication Services + Email Communication Services.
# Used for QA/QC email notifications to designated FG Ops Safety reviewers.
#
# Layout:
#   - Email Communication Service hosts email domains
#   - An Azure-managed domain provides a zero-config sender (e.g., donotreply@<guid>.azurecomm.net)
#     Custom domains can be added later without replacing the managed one
#   - Communication Service is the send API surface, linked to the email domain
#
# Managed identity from the Container App is granted "Contributor" on the
# Communication Service so email can be sent without API keys in code.

resource "azurerm_email_communication_service" "main" {
  name                = "ecs-${var.name_prefix}"
  resource_group_name = var.resource_group_name
  data_location       = var.data_location
  tags                = var.tags
}

resource "azurerm_email_communication_service_domain" "managed" {
  name              = "AzureManagedDomain"
  email_service_id  = azurerm_email_communication_service.main.id
  domain_management = "AzureManaged"
  tags              = var.tags
}

resource "azurerm_communication_service" "main" {
  name                = "acs-${var.name_prefix}"
  resource_group_name = var.resource_group_name
  data_location       = var.data_location
  tags                = var.tags
}

# Azure's provider does not currently expose a first-class resource for
# linking an Email domain to a Communication Service; the linkage is done
# at send time by passing the full resource path of the email domain as
# the sender. We export the domain's fully qualified name so the backend
# can construct the sender address.
