# Basics
variable "location" {
  type = string
  description = "Azure region of the analyst environment"
}

variable "project" {
  type = string
  description = "Name of the project"
}

variable "env" {
  type = string
  description = "Which environment - dev, qa, test, prod"
}

# From other module
variable "rg-name" {
  type = string
  description = "Name of the resource group"
}

variable "des-id" {
  type = string
  description = "ID of the disk encryption set"
}


# For this module

# Vnet
variable "vnet-address-space" {
  type = string
  description = "Address space, which is reserved in NHN IP plan"
}

# Subnet
variable "snet-address-prefix" {
  type = string
  description = "Subnet address prefix"
}

variable "snet-bastion-address-prefix" {
  type = string
  description = "Bastion subnet address prefix. Must be at least /27"
}

# NSG
## Deny All
variable "nsg-snet-vm-rule-block-priority" {
  type = number
  description = "NSG rule priority - Must be a higher number than the other defined rules to take effect"
}

## Allow Bastion
variable "nsg-snet-vm-rule-allowbastion-priority" {
  type = number
  description = "NSG rule priority"
  default = 100
}

## Allow Internal Subnet
variable "nsg-snet-vm-rule-allowinternalsubnet-priority" {
  type = number
  description = "NSG rule priority"
  default = 101
}

## Rule 1
variable "nsg-snet-vm-rule-1-name" {
  type = string
  description = "NSG Rule name"
}
variable "nsg-snet-vm-rule-1-access" {
  type = string
  description = "NSG Rule Access - Block or Allow"
}
variable "nsg-snet-vm-rule-1-direction" {
  type = string
  description = "NSG Rule Direction - Inbound or Outbound"
}
variable "nsg-snet-vm-rule-1-priority" {
  type = number
  description = "NSG Rule priority"
}
variable "nsg-snet-vm-rule-1-protocol" {
  type = string
  description = "NSG Rule protocol"
}
variable "nsg-snet-vm-rule-1-source-address-prefix" {
  type = string
  description = "NSG Rule Source address prefix"
}
variable "nsg-snet-vm-rule-1-source-port-range" {
  type = string
  description = "NSG Rule Source port range"
}
variable "nsg-snet-vm-rule-1-destination-address-prefix" {
  type = string
  description = "NSG Rule Destination address prefix"
}
variable "nsg-snet-vm-rule-1-destination-port-range" {
  type = string
  description = "NSG Rule Destination port range"
}

## Rule 2
variable "nsg-snet-vm-rule-2-name" {
  type = string
  description = "NSG Rule name"
}
variable "nsg-snet-vm-rule-2-access" {
  type = string
  description = "NSG Rule Access - Block or Allow"
}
variable "nsg-snet-vm-rule-2-direction" {
  type = string
  description = "NSG Rule Direction - Inbound or Outbound"
}
variable "nsg-snet-vm-rule-2-priority" {
  type = number
  description = "NSG Rule priority"
}
variable "nsg-snet-vm-rule-2-protocol" {
  type = string
  description = "NSG Rule protocol"
}
variable "nsg-snet-vm-rule-2-source-address-prefixes" {
  type = list(string)
  description = "NSG Rule Source address prefix"
}
variable "nsg-snet-vm-rule-2-source-port-range" {
  type = string
  description = "NSG Rule Source port range"
}
variable "nsg-snet-vm-rule-2-destination-address-prefix" {
  type = string
  description = "NSG Rule Destination address prefix"
}
variable "nsg-snet-vm-rule-2-destination-port-range" {
  type = string
  description = "NSG Rule Destination port range"
}

# VM OSM - Common
variable "vmadmin-role" {
  type = string
  description = "Object Id for the Azure AD group that should give VM Admin role"
}

variable "vmuser-role" {
  type = string
  description = "Object Id for the Azure AD group that should give VM Admin role"
}

variable "vm-monitoringreader-role" {
  type = string
  description = "Object Id for the Azure AD group that should give Monitoring Reader role"
}

variable "vm-linux-osm-ssh-pub-key" {
  type = string
  description = "Path to SSH Public key file"
}

variable "vm-linux-osm-image-publisher" {
  type = string
  description = "az vm image list --output table"
  default = "Canonical"
}
variable "vm-linux-osm-image-offer" {
  type = string
  description = "az vm image list --output table"
  default = "UbuntuServer"
}
variable "vm-linux-osm-image-sku" {
  type = string
  description = "az vm image list --output table"
  default = "18.04-LTS"
}
variable "vm-linux-osm-image-version" {
  type = string
  description = "az vm image list --output table"
  default = "latest"
}

variable "vm-linux-osm-disk-caching" {
  type = string
  description = "Possible values are None, ReadOnly and ReadWrite."
  default = "ReadWrite"
}
variable "vm-linux-osm-disk-type" {
  type = string
  description = "Possible values are Standard_LRS, StandardSSD_LRS and Premium_LRS"
  default = "Premium_LRS"
}

# VM OSM Overpass
variable "vm-linux-osm-overpass-count" {
  type = number
  default = "1"
  description = "Define number of VMs to be created"
}

variable "vm-linux-osm-overpass-static-private-ip" {
  type = string
  description = "Static IP address. WILL FAIL IF var.vm-linux-osm-overpass-count is >1"
}

variable "vm-linux-osm-overpass-name-prefix" {
  type = string
  description = "Prefix of the VM name. Will be followed with a number"
}

variable "vm-linux-osm-overpass-sku" {
  type = string
  description = "Define VM sku / size. For example Standard_DS1_v2. Check az vm list-skus -l westeurope"
}

variable "vm-linux-osm-overpass-datadisk-size" {
  type = string
  description = "Size of the data disk in GB"
}

variable "vm-linux-osm-overpass-datadisk-lun" {
  type = number
  description = "The Logical Unit Number of the Data Disk, which needs to be unique within the Virtual Machine"
  default = 10
}


# VM OSM Nominatim
variable "vm-linux-osm-nominatim-count" {
  type = number
  default = "1"
  description = "Define number of VMs to be created"
}

variable "vm-linux-osm-nominatim-static-private-ip" {
  type = string
  description = "Static IP address. WILL FAIL IF var.vm-linux-osm-nominatim-count is >1"
}

variable "vm-linux-osm-nominatim-name-prefix" {
  type = string
  description = "Prefix of the VM name. Will be followed with a number"
}

variable "vm-linux-osm-nominatim-sku" {
  type = string
  description = "Define VM sku / size. For example Standard_DS1_v2. Check az vm list-skus -l westeurope"
}

variable "vm-linux-osm-nominatim-datadisk-size" {
  type = string
  description = "Size of the data disk in GB"
}

variable "vm-linux-osm-nominatim-datadisk-lun" {
  type = number
  description = "The Logical Unit Number of the Data Disk, which needs to be unique within the Virtual Machine"
  default = 10
}
