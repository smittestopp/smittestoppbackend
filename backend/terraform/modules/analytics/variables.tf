#Basics
variable "location" {
  type        = string
  description = "Azure region of the analyst environment"
}

variable "project" {
  type        = string
  description = "Name of the project"
}

variable "env" {
  type        = string
  description = "Which environment - dev, qa, test, prod"
}

# Resource group permissions
variable "vmadmin-role" {
  type        = string
  description = "Object Id for the Azure AD group that should give VM Admin role"
}

variable "vmuser-role" {
  type        = string
  description = "Object Id for the Azure AD group that should give VM Admin role"
}

# Vnet
variable "vnet-address-space" {
  type        = string
  description = "Address space, which is reserved in NHN IP plan"
}

variable "snet-analytics-address-prefix" {
  type        = string
  description = "VM subnet address prefix"
}

variable "snet-bastion-address-prefix" {
  type        = string
  description = "Bastion subnet address prefix. Must be at least /27"
}

# NSG
## Deny All
variable "nsg-snet-vm-rule-block-priority" {
  type        = number
  description = "NSG rule priority - Must be a higher number than the other defined rules to take effect"
}

## Allow Bastion
variable "nsg-snet-vm-rule-allowbastion-priority" {
  type        = number
  description = "NSG rule priority"
  default     = 100
}

## Allow Internal Subnet
variable "nsg-snet-vm-rule-allowinternalsubnet-priority" {
  type        = number
  description = "NSG rule priority"
  default     = 101
}


# Key Vault
variable "kv-name" {
  type        = string
  description = "Name of the Key Vault"
}

# VM Linux Analytics
variable "vm-linux-analytics-count" {
  type        = number
  default     = "1"
  description = "Define number of VMs to be created"
}

variable "vm-linux-analytics-name-prefix" {
  type        = string
  description = "Prefix of the VM name. Will be followed with a number"
}

variable "vm-linux-analytics-sku" {
  type        = string
  description = "Define VM sku / size. For example Standard_DS1_v2. Check az vm list-skus -l westeurope"
}

variable "vm-linux-ssh-pub-key" {
  type        = string
  description = "Path to SSH Public key file"
}

## VM Linux Analytics - Image
# az vm image list --publisher Canonical --output table
variable "vm-linux-analytics-image-publisher" {
  type        = string
  description = "az vm image list --output table"
  default     = "Canonical"
}
variable "vm-linux-analytics-image-offer" {
  type        = string
  description = "az vm image list --output table"
  default     = "UbuntuServer"
}
variable "vm-linux-analytics-image-sku" {
  type        = string
  description = "az vm image list --output table"
  default     = "18.04-LTS"
}
variable "vm-linux-analytics-image-version" {
  type        = string
  description = "az vm image list --output table"
  default     = "latest"
}

## VM Linux Analytics - OS disk
variable "vm-linux-analytics-osdisk-caching" {
  type        = string
  description = "Possible values are None, ReadOnly and ReadWrite."
  default     = "ReadWrite"
}

variable "vm-linux-analytics-osdisk-type" {
  type        = string
  description = "Possible values are Standard_LRS, StandardSSD_LRS and Premium_LRS"
  default     = "StandardSSD_LRS" #Needed to use the NC6 Promo SKU. Can't use Premium_LRS
}


# VM Windows Jumphost
variable "vm-win-jumphost-count" {
  type        = number
  default     = "1"
  description = "Define number of VMs to be created"
}

variable "vm-win-jumphost-name-prefix" {
  type        = string
  description = "Prefix of the VM name. Will be followed with a number"
}

variable "vm-win-jumphost-sku" {
  type        = string
  description = "Define VM sku / size. For example Standard_DS1_v2. Check az vm list-skus -l northeurope"
}

variable "vm-win-jumphost-admin-pw" {
  type        = string
  description = "Admin pw"
}

## VM Windows Jumphost - Image
# az vm image list --publisher Microsoft --output table
variable "vm-win-jumphost-image-publisher" {
  type        = string
  description = "az vm image list --output table"
  default     = "microsoft-dsvm"
}
variable "vm-win-jumphost-image-offer" {
  type        = string
  description = "az vm image list --output table"
  default     = "dsvm-win-2019"
}
variable "vm-win-jumphost-image-sku" {
  type        = string
  description = "az vm image list --output table"
  default     = "server-2019"
}
variable "vm-win-jumphost-image-version" {
  type        = string
  description = "az vm image list --output table"
  default     = "latest"
}

## VM Windows Jumphost - OS disk
variable "vm-win-jumphost-osdisk-caching" {
  type        = string
  description = "Possible values are None, ReadOnly and ReadWrite."
  default     = "ReadWrite"
}

variable "vm-win-jumphost-osdisk-type" {
  type        = string
  description = "Possible values are Standard_LRS, StandardSSD_LRS and Premium_LRS"
  default     = "StandardSSD_LRS" #Needed to use the NC6 Promo SKU. Can't use Premium_LRS
}
