# Configure the Azure provider
provider "azurerm" {
  version         = "=2.4.0"
  subscription_id = var.subscription_id
  features {}
  }

# Configure the Azure storage backend
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-smittestopp-tfstate-prod"
    storage_account_name = "stsmittestopptfstateprod"
    container_name       = "tfstate"
    key                  = "soc-logs.terraform.tfstate"
  }
}

locals {
  project-env = "${var.project}-${var.env}"
}

# Create resource group
resource "azurerm_resource_group" "rg" {
  name     = "rg-${local.project-env}"
  location = var.location
}

# Storage account for the diagnostic logs
resource "azurerm_storage_account" "st-soc-logs" {
  location = var.location
  name = "st${var.storage-suffix}${var.env}"
  resource_group_name = azurerm_resource_group.rg.name

  account_replication_type = var.storage-replication-type
  account_tier = var.storage-account-tier
  account_kind = var.storage-account-kind
  access_tier = var.storage-access-tier

  network_rules {
    default_action = var.storage-network-rules-default-action
    ip_rules = var.storage-network-rules-ip-rules
  }
}
