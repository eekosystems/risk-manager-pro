output "communication_service_id" {
  value = azurerm_communication_service.main.id
}

output "communication_service_name" {
  value = azurerm_communication_service.main.name
}

output "communication_service_endpoint" {
  value = "https://${azurerm_communication_service.main.name}.communication.azure.com"
}

output "email_service_id" {
  value = azurerm_email_communication_service.main.id
}

output "email_sender_domain" {
  description = "FQDN of the Azure-managed sender domain (e.g., 1234abcd.azurecomm.net)"
  value       = azurerm_email_communication_service_domain.managed.mail_from_sender_domain
}

output "email_sender_address" {
  description = "Default donotreply sender address for system-generated emails"
  value       = "donotreply@${azurerm_email_communication_service_domain.managed.mail_from_sender_domain}"
}
