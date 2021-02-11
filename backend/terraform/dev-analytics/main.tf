# Configure the Azure provider
provider "azurerm" {
  version         = "=2.4.0"
  subscription_id = var.subscription_id
  features {}
}

# Configure the Azure storage backend
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-smittestopp-tfstate-dev"
    storage_account_name = "stsmittestopptfstatedev"
    container_name       = "tfstate"
    key                  = "dev-analytics.terraform.tfstate"
  }
}

module "analytics" {
  source = "../modules/analytics"

  # Basics
  location = "North Europe"
  project  = "smittestopp-analytics"
  env      = "dev"

  # Vnet
  vnet-address-space            = "10.200.0.0/16"
  snet-analytics-address-prefix = "10.200.0.0/24"
  snet-bastion-address-prefix   = "10.200.1.0/24"

  # Key Vault
  kv-name = "kv-smst-anl1-dev"

  # Groups that should have VM User Logins
  vmadmin-role = "" # A-FHI-Smittestopp-Dev-Analytics-VMAdminLogin
  vmuser-role  = "" # A-FHI-Smittestopp-Dev-Analytics-VMUserLogin

  # Linux Analytics VMs
  vm-linux-analytics-count       = 1
  vm-linux-analytics-name-prefix = "vmsmstlindev"
  #vm-linux-analytics-sku        = "Standard_DS1_v2"
  #vm-linux-analytics-sku        = "Standard_NC6_Promo"
  #vm-linux-analytics-sku        = "Standard_E32a_v4"
  vm-linux-analytics-sku         = "Standard_D15_v2"
  vm-linux-ssh-pub-key           = file("${path.root}/ssh-pub-keys/vmadmin.pub")

  # Windows Jumphost VMs
  vm-win-jumphost-count       = 1
  vm-win-jumphost-name-prefix = "vmsmstwindev"
  #vm-win-jumphost-sku        = "Standard_DS1_v2"
  vm-win-jumphost-sku         = "Standard_NC6_Promo"
  vm-win-jumphost-admin-pw    = var.vm-win-jumphost-admin-pw

  # NSG
  ## Block all
  nsg-snet-vm-rule-block-priority = 1000 # Must be a higher number than other custom rules
}
