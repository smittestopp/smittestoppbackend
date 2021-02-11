data "azurerm_client_config" "current" {}

locals {
  project-env = "${var.project}-${var.env}"
}

# Create resource group
resource "azurerm_resource_group" "rg" {
  name     = "rg-${local.project-env}"
  location = var.location
}

resource "azurerm_role_assignment" "rg-vmadmin-role" {
  principal_id         = var.vmadmin-role
  scope                = azurerm_resource_group.rg.id
  role_definition_name = "Virtual Machine Administrator Login"
}

resource "azurerm_role_assignment" "rg-vmuser-role" {
  principal_id         = var.vmuser-role
  scope                = azurerm_resource_group.rg.id
  role_definition_name = "Virtual Machine User Login"
}

# Create VNet
resource "azurerm_virtual_network" "vnet" {
  address_space       = [var.vnet-address-space]
  location            = var.location
  name                = "vnet-${local.project-env}"
  resource_group_name = azurerm_resource_group.rg.name
}

# Create Subnet for VMs
resource "azurerm_subnet" "snet-vm" {
  address_prefix       = var.snet-analytics-address-prefix
  name                 = "snet-${local.project-env}"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  service_endpoints    = ["Microsoft.Sql"]
}

# Create Subnet for Bastion host
resource "azurerm_subnet" "snet-bastion" {
  address_prefix       = var.snet-bastion-address-prefix
  name                 = "AzureBastionSubnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
}

# NSG for VM subnet
resource "azurerm_network_security_group" "nsg-snet-vm" {
  location            = var.location
  name                = "nsg-${azurerm_subnet.snet-vm.name}"
  resource_group_name = azurerm_resource_group.rg.name
}
resource "azurerm_subnet_network_security_group_association" "nsg-snet-vm-assoc" {
  network_security_group_id = azurerm_network_security_group.nsg-snet-vm.id
  subnet_id                 = azurerm_subnet.snet-vm.id
}
resource "azurerm_network_security_rule" "nsg-snet-vm-rule-denyall" {
  resource_group_name         = azurerm_resource_group.rg.name
  network_security_group_name = azurerm_network_security_group.nsg-snet-vm.name
  name                        = "Deny-All"

  access    = "Deny"
  direction = "Inbound"

  priority = var.nsg-snet-vm-rule-block-priority
  protocol = "*"

  source_address_prefix = "*"
  source_port_range     = "*"

  destination_address_prefix = "*"
  destination_port_range     = "*"
}

resource "azurerm_network_security_rule" "nsg-snet-vm-rule-allowbastion" {
  resource_group_name         = azurerm_resource_group.rg.name
  network_security_group_name = azurerm_network_security_group.nsg-snet-vm.name
  name                        = "Allow-RDP-SSH-From-Bastion"

  access    = "Allow"
  direction = "Inbound"

  priority = var.nsg-snet-vm-rule-allowbastion-priority
  protocol = "Tcp"

  source_address_prefix = azurerm_subnet.snet-bastion.address_prefix
  source_port_range     = "*"

  destination_address_prefix = azurerm_subnet.snet-vm.address_prefix
  destination_port_ranges    = ["22", "3389"]
}

resource "azurerm_network_security_rule" "nsg-snet-vm-rule-allowinternalsubnet" {
  resource_group_name         = azurerm_resource_group.rg.name
  network_security_group_name = azurerm_network_security_group.nsg-snet-vm.name
  name                        = "Allow-Traffic-Internal-Subnet"

  access    = "Allow"
  direction = "Inbound"

  priority = var.nsg-snet-vm-rule-allowinternalsubnet-priority
  protocol = "*"

  source_address_prefix = azurerm_subnet.snet-vm.address_prefix
  source_port_range     = "*"

  destination_address_prefix = azurerm_subnet.snet-vm.address_prefix
  destination_port_range     = "*"
}


# Bastion

## Public IP for the bastion host
resource "azurerm_public_ip" "pip-bastion" {
  location            = var.location
  name                = "pip-${var.project}-bastion-${var.env}"
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

## Create the bastion host
resource "azurerm_bastion_host" "bastion" {
  name                = "bastion-${local.project-env}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location

  ip_configuration {
    name                 = "bastion_ip_configuration"
    subnet_id            = azurerm_subnet.snet-bastion.id
    public_ip_address_id = azurerm_public_ip.pip-bastion.id
  }
}

## Give VM Users Reader role on the bastion
resource "azurerm_role_assignment" "bastion-vmadmin-reader-role" {
  principal_id         = var.vmadmin-role
  scope                = azurerm_bastion_host.bastion.id
  role_definition_name = "Reader"
}
resource "azurerm_role_assignment" "bastion-vmuser-reader-role" {
  principal_id         = var.vmuser-role
  scope                = azurerm_bastion_host.bastion.id
  role_definition_name = "Reader"
}

# Log Analytics

## Create a Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "la" {
  name                = "loganalytics-${local.project-env}"
  location            = "westeurope"
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

}

## Create a Automation Account
resource "azurerm_automation_account" "la-automation-account" {
  name                = "automationaccount-${local.project-env}"
  location            = azurerm_log_analytics_workspace.la.location
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "Basic"
}

## Link Log Analytics Workspace to Automation Account
resource "azurerm_log_analytics_linked_service" "la-linked-service" {
  resource_group_name = azurerm_resource_group.rg.name
  workspace_name      = azurerm_log_analytics_workspace.la.name
  resource_id         = azurerm_automation_account.la-automation-account.id
}

## Enable Update Management solution
resource "azurerm_log_analytics_solution" "la-solution-update" {
  depends_on = [
    azurerm_log_analytics_linked_service.la-linked-service
  ]
  solution_name         = "Updates"
  location              = azurerm_log_analytics_workspace.la.location
  resource_group_name   = azurerm_resource_group.rg.name
  workspace_resource_id = azurerm_log_analytics_workspace.la.id
  workspace_name        = azurerm_log_analytics_workspace.la.name

  plan {
    publisher = "Microsoft"
    product   = "OMSGallery/Updates"
  }
}


# Disk encryption
# https://docs.microsoft.com/en-us/azure/virtual-machines/linux/disk-encryption

## Create KeyVault for use with the disk encryption set
resource "azurerm_key_vault" "kv" {
  location            = var.location
  name                = var.kv-name
  resource_group_name = azurerm_resource_group.rg.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  soft_delete_enabled      = true
  purge_protection_enabled = true

  /*
  access_policy {
    object_id = ""
    tenant_id = ""
  }
  */
}

## Create key in Key Vault
resource "azurerm_key_vault_key" "kv-key-des" {
  name         = "key-des-${local.project-env}"
  key_vault_id = azurerm_key_vault.kv.id
  key_type     = "RSA"
  key_size     = 2048

  key_opts = [
    "decrypt",
    "encrypt",
    "sign",
    "unwrapKey",
    "verify",
    "wrapKey",
  ]
}

## Create Disk Encryption Set
resource "azurerm_disk_encryption_set" "des" {
  name                = "des-${local.project-env}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  key_vault_key_id    = azurerm_key_vault_key.kv-key-des.id

  identity {
    type = "SystemAssigned"
  }
}

## Give the Disk Encryption Set app Reader role on the resource group
resource "azurerm_role_assignment" "des-app" {
  principal_id         = azurerm_disk_encryption_set.des.identity[0].principal_id
  scope                = azurerm_resource_group.rg.id
  role_definition_name = "Reader"
}

## Give yourself access to create key in Key Vault
resource "azurerm_key_vault_access_policy" "kv-access-policy-self" {
  key_vault_id = azurerm_key_vault.kv.id
  object_id    = data.azurerm_client_config.current.object_id
  tenant_id    = data.azurerm_client_config.current.tenant_id

  key_permissions = [
    "create",
    "get",
    "delete",
    "list",
    "wrapkey",
    "unwrapkey",
    "get",
  ]
}

## Give the Disk Encryption Set app access to the key in Key Vault
resource "azurerm_key_vault_access_policy" "kv-access-policy-des" {
  depends_on = [azurerm_key_vault_access_policy.kv-access-policy-self]

  key_vault_id = azurerm_key_vault.kv.id
  object_id    = azurerm_disk_encryption_set.des.identity[0].principal_id
  tenant_id    = data.azurerm_client_config.current.tenant_id

  key_permissions = [
    "get",
    "wrapkey",
    "unwrapkey",
  ]
}

# Create Analytic VMs

## Create NIC
resource "azurerm_network_interface" "nic-vm-linux-analytics" {
  count               = var.vm-linux-analytics-count
  location            = var.location
  name                = "nic-${var.vm-linux-analytics-name-prefix}-${count.index + 1}"
  resource_group_name = azurerm_resource_group.rg.name
  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.snet-vm.id
    private_ip_address_allocation = "Dynamic"
  }
}

## Create the analytics VMs
resource "azurerm_linux_virtual_machine" "vm-linux-analytics" {
  depends_on = [azurerm_key_vault_access_policy.kv-access-policy-des]

  count                 = var.vm-linux-analytics-count
  location              = var.location
  resource_group_name   = azurerm_resource_group.rg.name
  name                  = "${var.vm-linux-analytics-name-prefix}-${count.index + 1}"
  network_interface_ids = [azurerm_network_interface.nic-vm-linux-analytics[count.index].id]
  size                  = var.vm-linux-analytics-sku

  admin_username = "vmadmin"
  admin_ssh_key {
    username   = "vmadmin"
    public_key = var.vm-linux-ssh-pub-key
  }

  source_image_reference {
    publisher = var.vm-linux-analytics-image-publisher
    offer     = var.vm-linux-analytics-image-offer
    sku       = var.vm-linux-analytics-image-sku
    version   = var.vm-linux-analytics-image-version
  }

  os_disk {
    name                   = "disk-os-${var.vm-linux-analytics-name-prefix}-${count.index + 1}"
    caching                = var.vm-linux-analytics-osdisk-caching
    storage_account_type   = var.vm-linux-analytics-osdisk-type
    disk_encryption_set_id = azurerm_disk_encryption_set.des.id
  }

  # Adds ignore_changes because sometimes the disk encryption set is updated, and Terraforms make the VM boot because it's trying to change it back
  lifecycle {
    ignore_changes = [os_disk]
  }
}

## VM Extensions for the analytics VM
# Azure CLI: az vm extension image list --location northeurope --output table
# Name ("type" in Terraform)           Publisher                                             Version
# -----------------------------------  ----------------------------------------------------  ----------------
# DependencyAgentLinux                 Microsoft.Azure.Monitoring.DependencyAgent            9.9.1.7050
# OmsAgentForLinux                     Microsoft.EnterpriseCloud.Monitoring                  1.9.1
# LinuxAgent.AzureSecurityCenter       Qualys                                                1.0.0.3
# AADLoginForLinux                     Microsoft.Azure.ActiveDirectory.LinuxSSH              1.0.8370001
# CustomScript                         Microsoft.Azure.Extensions                            2.1.3
resource "azurerm_virtual_machine_extension" "vm-extension-DependencyAgentLinux" {
  count                      = var.vm-linux-analytics-count
  name                       = "DependencyAgentLinux"
  virtual_machine_id         = azurerm_linux_virtual_machine.vm-linux-analytics[count.index].id
  publisher                  = "Microsoft.Azure.Monitoring.DependencyAgent"
  type                       = "DependencyAgentLinux"
  type_handler_version       = "9.9"
  auto_upgrade_minor_version = true
}

# Needed for Azure AD Authentication
# https://docs.microsoft.com/en-us/azure/virtual-machines/linux/login-using-aad
resource "azurerm_virtual_machine_extension" "vm-extension-AADLoginForLinux" {
  count                      = var.vm-linux-analytics-count
  name                       = "AADLoginForLinux"
  virtual_machine_id         = azurerm_linux_virtual_machine.vm-linux-analytics[count.index].id
  publisher                  = "Microsoft.Azure.ActiveDirectory.LinuxSSH"
  type                       = "AADLoginForLinux"
  type_handler_version       = "1.0"
  auto_upgrade_minor_version = true
}

# Create Windows VM for use as a jump station to Linux VMs with bastion
## Create NIC
resource "azurerm_network_interface" "nic-vm-win-jumphost" {
  count               = var.vm-win-jumphost-count
  location            = var.location
  name                = "nic-${var.vm-win-jumphost-name-prefix}-${count.index + 1}"
  resource_group_name = azurerm_resource_group.rg.name
  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.snet-vm.id
    private_ip_address_allocation = "Dynamic"
  }
}

## Create the VM(s)
resource "azurerm_windows_virtual_machine" "vm-win-jumphost" {
  depends_on = [azurerm_key_vault_access_policy.kv-access-policy-des]

  count                 = var.vm-win-jumphost-count
  location              = var.location
  resource_group_name   = azurerm_resource_group.rg.name
  name                  = "${var.vm-win-jumphost-name-prefix}-${count.index + 1}"
  network_interface_ids = [azurerm_network_interface.nic-vm-win-jumphost[count.index].id]
  size                  = var.vm-win-jumphost-sku
  license_type          = "Windows_Server"

  admin_username = "vmadmin"
  admin_password = var.vm-win-jumphost-admin-pw

  source_image_reference {
    publisher = var.vm-win-jumphost-image-publisher
    offer     = var.vm-win-jumphost-image-offer
    sku       = var.vm-win-jumphost-image-sku
    version   = var.vm-win-jumphost-image-version
  }

  os_disk {
    name                   = "disk-os-${var.vm-win-jumphost-name-prefix}-${count.index + 1}"
    caching                = var.vm-win-jumphost-osdisk-caching
    storage_account_type   = var.vm-win-jumphost-osdisk-type
    disk_encryption_set_id = azurerm_disk_encryption_set.des.id
  }

  # Adds ignore_changes because sometimes the disk encryption set is updated, and Terraforms make the VM boot because it's trying to change it back
  lifecycle {
    ignore_changes = [os_disk]
  }
}
