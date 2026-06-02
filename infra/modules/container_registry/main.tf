resource "azurerm_container_registry" "main" {
  name                = replace("acr${var.name_prefix}", "-", "")
  resource_group_name = var.resource_group_name
  location            = var.location
  # M-13: SKU is a variable so the free hardening below lands on Basic now, with
  # zero added cost. Premium (~10x Basic) is what unlocks network rules, private
  # endpoints, and the quarantine policy — flip acr_sku to "Premium" only when
  # ready to pay for those. quarantine_policy_enabled then becomes effective too.
  sku = var.acr_sku
  # No shared admin credentials — pull/push authenticates via Entra/managed
  # identity RBAC (AcrPull is granted to the Container App identity). Free on Basic.
  admin_enabled = false
  # M-13: never serve unauthenticated pulls. Free on Basic.
  anonymous_pull_enabled = false
  # Public access stays on (Basic has no private-link option anyway); closing it
  # is a Premium + private-endpoint change tracked with H-10/M-9.
  public_network_access_enabled = var.public_network_access_enabled
  # Premium-only; gated default-off so it is inert on Basic and can't break the
  # deploy pull before a scanner is wired in.
  quarantine_policy_enabled = var.quarantine_policy_enabled
  tags                      = var.tags

  # Note: Docker Content Trust (Notary v1) is intentionally not enabled — Azure
  # has retired it. Image signing should move to Notation/Notary v2 + cosign,
  # which is an ACR Tasks/pipeline change rather than a registry attribute.
}
