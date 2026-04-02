terraform {
  backend "azurerm" {
    resource_group_name  = "rmp-terraform-state"
    storage_account_name = "rmpfgllctfstate"
    container_name       = "tfstate"
    key                  = "riskmanagerpro.terraform.tfstate"
  }
}
