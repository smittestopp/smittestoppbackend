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
    key                  = "prod-analytics.terraform.tfstate"
  }
}

module "analytics" {
  source = "../modules/analytics"

  # Basics
  location = "North Europe"
  project  = "smittestopp-analytics"
  env      = "prod"

  # Vnet
  vnet-address-space            = "10.200.0.0/16"
  snet-analytics-address-prefix = "10.200.0.0/24"
  snet-bastion-address-prefix   = "10.200.1.0/24"

  # Key Vault
  kv-name = "kv-smst-anl1-prod"

  # Groups that should have VM User Logins
  vmadmin-role = "" # A-FHI-Smittestopp-Prod-Analytics-VMAdminLogin
  vmuser-role  = "" # A-FHI-Smittestopp-Prod-Analytics-VMUserLogin

  # Linux Analytics VMs
  vm-linux-analytics-count       = 1
  vm-linux-analytics-name-prefix = "vmsmstlinprod"
  vm-linux-analytics-sku         = "Standard_D2_v3"
  #vm-linux-analytics-sku        = "Standard_NC6_Promo"
  #vm-linux-analytics-sku        = "Standard_E32a_v4"
  #vm-linux-analytics-sku        = "Standard_D15_v2"
  vm-linux-ssh-pub-key           = file("${path.root}/ssh-pub-keys/vmadmin.pub")

  # Windows Jumphost VMs
  vm-win-jumphost-count       = 1
  vm-win-jumphost-name-prefix = "vmsmstwinprod"
  vm-win-jumphost-sku         = "Standard_NC6_Promo"
  vm-win-jumphost-admin-pw    = var.vm-win-jumphost-admin-pw

  # NSG
  ## Block all
  nsg-snet-vm-rule-block-priority = 1000 # Must be a higher number than other custom rules
}

module "osm" {
  source = "../modules/osm"

  # From other module
  rg-name = module.analytics.rg-name
  des-id  = module.analytics.des-id
  #vnet-name = module.analytics.vnet-name

  # Basics
  location = "North Europe"
  project  = "smittestopp-osm"
  env      = "prod"

  # Vnet
  vnet-address-space          = "172.16.0.0/16"
  snet-address-prefix         = "172.16.1.0/24"
  snet-bastion-address-prefix = "172.16.0.0/24"

  # NSG
  ## Block all
  nsg-snet-vm-rule-block-priority = 1000 # Must be a higher number than other custom rules

  ## Rule 1
  nsg-snet-vm-rule-1-name      = "Allow-8888-From-AKS-Prod"
  nsg-snet-vm-rule-1-access    = "Allow"
  nsg-snet-vm-rule-1-direction = "Inbound"
  nsg-snet-vm-rule-1-priority  = 300
  nsg-snet-vm-rule-1-protocol  = "Tcp"

  nsg-snet-vm-rule-1-source-address-prefix = "10.240.0.0/16"
  nsg-snet-vm-rule-1-source-port-range     = "*"

  nsg-snet-vm-rule-1-destination-address-prefix = module.osm.snet-osm-address-prefix
  nsg-snet-vm-rule-1-destination-port-range     = "8888"

  ## Rule 2
  nsg-snet-vm-rule-2-name      = "Allow-8888-From-Dev-Analytics-Public"
  nsg-snet-vm-rule-2-access    = "Allow"
  nsg-snet-vm-rule-2-direction = "Inbound"
  nsg-snet-vm-rule-2-priority  = 400
  nsg-snet-vm-rule-2-protocol  = "Tcp"

  nsg-snet-vm-rule-2-source-address-prefixes = ["1.2.3.4"]
  nsg-snet-vm-rule-2-source-port-range       = "*"

  nsg-snet-vm-rule-2-destination-address-prefix = module.osm.snet-osm-address-prefix
  nsg-snet-vm-rule-2-destination-port-range     = "8888"


  # Groups that should have VM User Logins
  vmadmin-role             = "" # A-FHI-Smittestopp-Prod-OSM-VMAdminLogin
  vmuser-role              = "" # A-FHI-Smittestopp-Prod-OSM-VMUserLogin
  vm-monitoringreader-role = "" # A-FHI-Smittestopp-Prod-OSM-MonitoringReader

  # Linux VMs common
  vm-linux-osm-ssh-pub-key = file("${path.root}/ssh-pub-keys/vmadmin.pub")

  # Linux OSM Overpass VMs
  vm-linux-osm-overpass-name-prefix       = "vm-smst-osm-overp-prod"
  vm-linux-osm-overpass-static-private-ip = "172.16.1.4" # !!!! Won't work if count is set to >1
  #vm-linux-osm-overpass-sku              = "Standard_D32s_v3" # 32vCPU + 128 GB RAM
  vm-linux-osm-overpass-sku               = "Standard_D4s_v3"
  vm-linux-osm-overpass-datadisk-size     = "512" # In GB

  # Linux OSM Nominatim VMs
  vm-linux-osm-nominatim-name-prefix       = "vm-smst-osm-nomi-prod"
  vm-linux-osm-nominatim-static-private-ip = "172.16.1.5" # !!!! Won't work if count is set to >1
  #vm-linux-osm-nominatim-sku              = "Standard_DS13_v2" # 8vCPU + 56 GB RAM
  vm-linux-osm-nominatim-sku               = "Standard_D4s_v3"
  vm-linux-osm-nominatim-datadisk-size     = "1024" # In GB
}
