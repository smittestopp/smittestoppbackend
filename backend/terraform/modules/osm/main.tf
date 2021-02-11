data "azurerm_client_config" "current" {}

locals {
  project-env = "${var.project}-${var.env}"
}


# Create VNet
resource "azurerm_virtual_network" "vnet" {
  address_space = [var.vnet-address-space]
  location = var.location
  name = "vnet-${local.project-env}"
  resource_group_name = var.rg-name
}

# Create subnet for VMs
resource "azurerm_subnet" "snet-vm" {
  address_prefix = var.snet-address-prefix
  name = "snet-${local.project-env}"
  resource_group_name = var.rg-name
  virtual_network_name = azurerm_virtual_network.vnet.name
  #virtual_network_name = var.vnet-name
}

# Create Subnet for Bastion host
resource "azurerm_subnet" "snet-bastion" {
  address_prefix = var.snet-bastion-address-prefix
  name = "AzureBastionSubnet"
  resource_group_name = var.rg-name
  virtual_network_name = azurerm_virtual_network.vnet.name
}


# NSG for subnet
resource "azurerm_network_security_group" "nsg-snet-vm" {
  location = var.location
  name = "nsg-${azurerm_subnet.snet-vm.name}"
  resource_group_name = var.rg-name
}
resource "azurerm_subnet_network_security_group_association" "nsg-snet-vm-assoc" {
  network_security_group_id = azurerm_network_security_group.nsg-snet-vm.id
  subnet_id = azurerm_subnet.snet-vm.id
}
resource "azurerm_network_security_rule" "nsg-snet-vm-rule-denyall" {
  resource_group_name = var.rg-name
  network_security_group_name = azurerm_network_security_group.nsg-snet-vm.name
  name = "Deny-All"

  access = "Deny"
  direction = "Inbound"

  priority = var.nsg-snet-vm-rule-block-priority
  protocol = "*"

  source_address_prefix = "*"
  source_port_range = "*"

  destination_address_prefix = "*"
  destination_port_range = "*"
}

resource "azurerm_network_security_rule" "nsg-snet-vm-rule-allowbastion" {
  resource_group_name = var.rg-name
  network_security_group_name = azurerm_network_security_group.nsg-snet-vm.name
  name = "Allow-RDP-SSH-From-Bastion"

  access = "Allow"
  direction = "Inbound"

  priority = var.nsg-snet-vm-rule-allowbastion-priority
  protocol = "Tcp"

  source_address_prefix = var.snet-bastion-address-prefix
  source_port_range = "*"

  destination_address_prefix = azurerm_subnet.snet-vm.address_prefix
  destination_port_ranges = ["22","3389"]
}

resource "azurerm_network_security_rule" "nsg-snet-vm-rule-allowinternalsubnet" {
  resource_group_name = var.rg-name
  network_security_group_name = azurerm_network_security_group.nsg-snet-vm.name
  name = "Allow-Traffic-Internal-Subnet"

  access = "Allow"
  direction = "Inbound"

  priority = var.nsg-snet-vm-rule-allowinternalsubnet-priority
  protocol = "*"

  source_address_prefix = azurerm_subnet.snet-vm.address_prefix
  source_port_range = "*"

  destination_address_prefix = azurerm_subnet.snet-vm.address_prefix
  destination_port_range = "*"
}

resource "azurerm_network_security_rule" "nsg-snet-vm-rule-1" {
  resource_group_name = var.rg-name
  network_security_group_name = azurerm_network_security_group.nsg-snet-vm.name
  name = var.nsg-snet-vm-rule-1-name

  access = var.nsg-snet-vm-rule-1-access
  direction = var.nsg-snet-vm-rule-1-direction

  priority = var.nsg-snet-vm-rule-1-priority
  protocol = var.nsg-snet-vm-rule-1-protocol

  source_address_prefix = var.nsg-snet-vm-rule-1-source-address-prefix
  source_port_range = var.nsg-snet-vm-rule-1-source-port-range

  destination_address_prefix = var.nsg-snet-vm-rule-1-destination-address-prefix
  destination_port_range = var.nsg-snet-vm-rule-1-destination-port-range
}

resource "azurerm_network_security_rule" "nsg-snet-vm-rule-2" {
  resource_group_name = var.rg-name
  network_security_group_name = azurerm_network_security_group.nsg-snet-vm.name
  name = var.nsg-snet-vm-rule-2-name

  access = var.nsg-snet-vm-rule-2-access
  direction = var.nsg-snet-vm-rule-2-direction

  priority = var.nsg-snet-vm-rule-2-priority
  protocol = var.nsg-snet-vm-rule-2-protocol

  source_address_prefixes = var.nsg-snet-vm-rule-2-source-address-prefixes
  source_port_range = var.nsg-snet-vm-rule-2-source-port-range

  destination_address_prefix = var.nsg-snet-vm-rule-2-destination-address-prefix
  destination_port_range = var.nsg-snet-vm-rule-2-destination-port-range
}


# Bastion

## Public IP for the bastion host
resource "azurerm_public_ip" "pip-bastion" {
  location = var.location
  name = "pip-${var.project}-bastion-${var.env}"
  resource_group_name = var.rg-name
  allocation_method = "Static"
  sku = "Standard"
}

## Create the bastion host
resource "azurerm_bastion_host" "bastion" {
  name = "bastion-${local.project-env}"
  resource_group_name = var.rg-name
  location = var.location

  ip_configuration {
    name = "bastion_ip_configuration"
    subnet_id = azurerm_subnet.snet-bastion.id
    public_ip_address_id = azurerm_public_ip.pip-bastion.id
  }
}

## Give VM Users Reader role on the bastion
resource "azurerm_role_assignment" "bastion-vmadmin-reader-role" {
  principal_id = var.vmadmin-role
  scope = azurerm_bastion_host.bastion.id
  role_definition_name = "Reader"
}
resource "azurerm_role_assignment" "bastion-vmuser-reader-role" {
  principal_id = var.vmuser-role
  scope = azurerm_bastion_host.bastion.id
  role_definition_name = "Reader"
}

# Create VM - Linux OSM Overpass

## Create Public IP
resource "azurerm_public_ip" "pip-vm-linux-osm-overpass" {
  count = var.vm-linux-osm-overpass-count
  location = var.location
  name = "pip-${var.vm-linux-osm-overpass-name-prefix}-${count.index + 1}"
  resource_group_name = var.rg-name
  allocation_method = "Static"
}

## Create NIC
resource "azurerm_network_interface" "nic-vm-linux-osm-overpass" {
  count = var.vm-linux-osm-overpass-count
  location = var.location
  name = "nic-${var.vm-linux-osm-overpass-name-prefix}-${count.index + 1}"
  resource_group_name = var.rg-name
  ip_configuration {
    name = "ipconfig1"
    subnet_id = azurerm_subnet.snet-vm.id
    private_ip_address_allocation = "Static"
    private_ip_address = var.vm-linux-osm-overpass-static-private-ip # !!!! Won't work if count is set to >1
    public_ip_address_id = azurerm_public_ip.pip-vm-linux-osm-overpass[count.index].id
  }
}

## Create the VM
resource "azurerm_linux_virtual_machine" "vm-linux-osm-overpass" {
  #depends_on = [azurerm_key_vault_access_policy.kv-access-policy-des]

  count = var.vm-linux-osm-overpass-count
  location = var.location
  resource_group_name = var.rg-name
  name = "${var.vm-linux-osm-overpass-name-prefix}-${count.index + 1}"
  network_interface_ids = [azurerm_network_interface.nic-vm-linux-osm-overpass[count.index].id]
  size = var.vm-linux-osm-overpass-sku

  admin_username = "vmadmin"
  admin_ssh_key {
    username = "vmadmin"
    public_key = var.vm-linux-osm-ssh-pub-key
  }

  source_image_reference {
    publisher = var.vm-linux-osm-image-publisher
    offer = var.vm-linux-osm-image-offer
    sku = var.vm-linux-osm-image-sku
    version = var.vm-linux-osm-image-version
  }

  os_disk {
    name = "disk-os-${var.vm-linux-osm-overpass-name-prefix}-${count.index + 1}"
    caching = var.vm-linux-osm-disk-caching
    storage_account_type = var.vm-linux-osm-disk-type
    disk_encryption_set_id = var.des-id
  }

  # Adds ignore_changes because sometimes the disk encryption set is updated, and Terraforms make the VM boot because it's trying to change it back
  # Added also source_image_reference, identity and priority. Needed to add this after the fix with changing vnet. Had to recreate the VM and reuse both the os disk and data disk
  lifecycle {
    ignore_changes = [os_disk, source_image_reference, identity, priority]
  }
}

## Data disk
resource "azurerm_managed_disk" "datadisk-vm-linux-osm-overpass" {
  count = var.vm-linux-osm-overpass-count
  name = "disk-data-${var.vm-linux-osm-overpass-name-prefix}-${count.index + 1}"
  location = var.location
  resource_group_name = var.rg-name

  create_option = "Empty"
  storage_account_type = var.vm-linux-osm-disk-type

  disk_encryption_set_id = var.des-id

  disk_size_gb = var.vm-linux-osm-overpass-datadisk-size
}

resource "azurerm_virtual_machine_data_disk_attachment" "datadisk-attachment-vm-linux-osm-overpass" {
  count = var.vm-linux-osm-overpass-count
  managed_disk_id = azurerm_managed_disk.datadisk-vm-linux-osm-overpass[count.index].id
  virtual_machine_id = azurerm_linux_virtual_machine.vm-linux-osm-overpass[count.index].id

  caching = var.vm-linux-osm-disk-caching
  lun = var.vm-linux-osm-overpass-datadisk-lun
}

## Role assignments to the VM
resource "azurerm_role_assignment" "vm-linux-osm-overpass-role-vmadmin" {
  count = var.vm-linux-osm-overpass-count
  principal_id = var.vmadmin-role
  scope = azurerm_linux_virtual_machine.vm-linux-osm-overpass[count.index].id
  role_definition_name = "Virtual Machine Administrator Login"
}

resource "azurerm_role_assignment" "vm-linux-osm-overpass-role-vmuser" {
  count = var.vm-linux-osm-overpass-count
  principal_id = var.vmuser-role
  scope = azurerm_linux_virtual_machine.vm-linux-osm-overpass[count.index].id
  role_definition_name = "Virtual Machine User Login"
}

resource "azurerm_role_assignment" "vm-linux-osm-overpass-role-monitoringreader" {
  count = var.vm-linux-osm-overpass-count
  principal_id = var.vm-monitoringreader-role
  scope = azurerm_linux_virtual_machine.vm-linux-osm-overpass[count.index].id
  role_definition_name = "Monitoring Reader"
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
resource "azurerm_virtual_machine_extension" "vm-linux-osm-overpass-extension-DependencyAgentLinux" {
  count = var.vm-linux-osm-overpass-count
  name = "DependencyAgentLinux"
  virtual_machine_id = azurerm_linux_virtual_machine.vm-linux-osm-overpass[count.index].id
  publisher = "Microsoft.Azure.Monitoring.DependencyAgent"
  type = "DependencyAgentLinux"
  type_handler_version = "9.9"
  auto_upgrade_minor_version = true
}

# Needed for Azure AD Authentication
# https://docs.microsoft.com/en-us/azure/virtual-machines/linux/login-using-aad
resource "azurerm_virtual_machine_extension" "vm-linux-osm-overpass-extension-AADLoginForLinux" {
  count = var.vm-linux-osm-overpass-count
  name = "AADLoginForLinux"
  virtual_machine_id = azurerm_linux_virtual_machine.vm-linux-osm-overpass[count.index].id
  publisher = "Microsoft.Azure.ActiveDirectory.LinuxSSH"
  type = "AADLoginForLinux"
  type_handler_version = "1.0"
  auto_upgrade_minor_version = true
}


# Create VM - Linux OSM Nominatim

## Create Public IP
resource "azurerm_public_ip" "pip-vm-linux-osm-nominatim" {
  count = var.vm-linux-osm-nominatim-count
  location = var.location
  name = "pip-${var.vm-linux-osm-nominatim-name-prefix}-${count.index + 1}"
  resource_group_name = var.rg-name
  allocation_method = "Static"
}

## Create NIC
resource "azurerm_network_interface" "nic-vm-linux-osm-nominatim" {
  count = var.vm-linux-osm-nominatim-count
  location = var.location
  name = "nic-${var.vm-linux-osm-nominatim-name-prefix}-${count.index + 1}"
  resource_group_name = var.rg-name
  ip_configuration {
    name = "ipconfig1"
    subnet_id = azurerm_subnet.snet-vm.id
    private_ip_address_allocation = "Static"
    private_ip_address = var.vm-linux-osm-nominatim-static-private-ip # !!!! Won't work if count is set to >1
    public_ip_address_id = azurerm_public_ip.pip-vm-linux-osm-nominatim[count.index].id
  }
}

## Create the VM
resource "azurerm_linux_virtual_machine" "vm-linux-osm-nominatim" {
  #depends_on = [azurerm_key_vault_access_policy.kv-access-policy-des]

  count = var.vm-linux-osm-nominatim-count
  location = var.location
  resource_group_name = var.rg-name
  name = "${var.vm-linux-osm-nominatim-name-prefix}-${count.index + 1}"
  network_interface_ids = [azurerm_network_interface.nic-vm-linux-osm-nominatim[count.index].id]
  size = var.vm-linux-osm-nominatim-sku

  admin_username = "vmadmin"
  admin_ssh_key {
    username = "vmadmin"
    public_key = var.vm-linux-osm-ssh-pub-key
  }

  source_image_reference {
    publisher = var.vm-linux-osm-image-publisher
    offer = var.vm-linux-osm-image-offer
    sku = var.vm-linux-osm-image-sku
    version = var.vm-linux-osm-image-version
  }

  os_disk {
    name = "disk-os-${var.vm-linux-osm-nominatim-name-prefix}-${count.index + 1}"
    caching = var.vm-linux-osm-disk-caching
    storage_account_type = var.vm-linux-osm-disk-type
    disk_encryption_set_id = var.des-id
  }

  # Adds ignore_changes because sometimes the disk encryption set is updated, and Terraforms make the VM boot because it's trying to change it back
  # Added also source_image_reference, identity and priority. Needed to add this after the fix with changing vnet. Had to recreate the VM and reuse both the os disk and data disk
  lifecycle {
    ignore_changes = [os_disk, source_image_reference, identity, priority]
  }
}

## Data disk
resource "azurerm_managed_disk" "datadisk-vm-linux-osm-nominatim" {
  count = var.vm-linux-osm-nominatim-count
  name = "disk-data-${var.vm-linux-osm-nominatim-name-prefix}-${count.index + 1}"
  location = var.location
  resource_group_name = var.rg-name

  create_option = "Empty"
  storage_account_type = var.vm-linux-osm-disk-type

  disk_encryption_set_id = var.des-id

  disk_size_gb = var.vm-linux-osm-nominatim-datadisk-size
}

resource "azurerm_virtual_machine_data_disk_attachment" "datadisk-attachment-vm-linux-osm-nominatim" {
  count = var.vm-linux-osm-nominatim-count
  managed_disk_id = azurerm_managed_disk.datadisk-vm-linux-osm-nominatim[count.index].id
  virtual_machine_id = azurerm_linux_virtual_machine.vm-linux-osm-nominatim[count.index].id

  caching = var.vm-linux-osm-disk-caching
  lun = var.vm-linux-osm-nominatim-datadisk-lun

  # Needed to add this after the fix with changing vnet. Had to recreate the VM and reuse both the os disk and data disk
  lifecycle {
    ignore_changes = [id, managed_disk_id, virtual_machine_id]
  }
}

resource "azurerm_role_assignment" "vm-linux-osm-nominatim-role-vmadmin" {
  count = var.vm-linux-osm-nominatim-count
  principal_id = var.vmadmin-role
  scope = azurerm_linux_virtual_machine.vm-linux-osm-nominatim[count.index].id
  role_definition_name = "Virtual Machine Administrator Login"
}

resource "azurerm_role_assignment" "vm-linux-osm-nominatim-role-vmuser" {
  count = var.vm-linux-osm-nominatim-count
  principal_id = var.vmuser-role
  scope = azurerm_linux_virtual_machine.vm-linux-osm-nominatim[count.index].id
  role_definition_name = "Virtual Machine User Login"
}

resource "azurerm_role_assignment" "vm-linux-osm-nominatim-role-monitoringreader" {
  count = var.vm-linux-osm-nominatim-count
  principal_id = var.vm-monitoringreader-role
  scope = azurerm_linux_virtual_machine.vm-linux-osm-nominatim[count.index].id
  role_definition_name = "Monitoring Reader"
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
resource "azurerm_virtual_machine_extension" "vm-linux-osm-nominatim-extension-DependencyAgentLinux" {
  count = var.vm-linux-osm-overpass-count
  name = "DependencyAgentLinux"
  virtual_machine_id = azurerm_linux_virtual_machine.vm-linux-osm-nominatim[count.index].id
  publisher = "Microsoft.Azure.Monitoring.DependencyAgent"
  type = "DependencyAgentLinux"
  type_handler_version = "9.9"
  auto_upgrade_minor_version = true
}

# Needed for Azure AD Authentication
# https://docs.microsoft.com/en-us/azure/virtual-machines/linux/login-using-aad
resource "azurerm_virtual_machine_extension" "vm-linux-osm-nominatim-extension-AADLoginForLinux" {
  count = var.vm-linux-osm-overpass-count
  name = "AADLoginForLinux"
  virtual_machine_id = azurerm_linux_virtual_machine.vm-linux-osm-nominatim[count.index].id
  publisher = "Microsoft.Azure.ActiveDirectory.LinuxSSH"
  type = "AADLoginForLinux"
  type_handler_version = "1.0"
  auto_upgrade_minor_version = true
}



#### DON'T NEED THE DISK ENCRYPTION SET. REUSES THE ONE FROM ANALYTICS MODULE ####

/*
# Disk encryption
# https://docs.microsoft.com/en-us/azure/virtual-machines/linux/disk-encryption

## Create KeyVault for use with the disk encryption set
resource "azurerm_key_vault" "kv" {
  location = var.location
  name = var.kv-name
  resource_group_name = azurerm_resource_group.rg.name
  tenant_id = data.azurerm_client_config.current.tenant_id
  sku_name = "standard"

  soft_delete_enabled         = true
  purge_protection_enabled    = true
}

## Create key in Key Vault
resource "azurerm_key_vault_key" "kv-key-des" {
  name = "key-des-${local.project-env}"
  key_vault_id = azurerm_key_vault.kv.id
  key_type = "RSA"
  key_size = 2048

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
  name = "des-${local.project-env}"
  location = var.location
  resource_group_name = azurerm_resource_group.rg.name
  key_vault_key_id = azurerm_key_vault_key.kv-key-des.id

  identity {
    type = "SystemAssigned"
  }
}

## Give the Disk Encryption Set app Reader role on the resource group
resource "azurerm_role_assignment" "des-app" {
  principal_id = azurerm_disk_encryption_set.des.identity[0].principal_id
  scope = azurerm_resource_group.rg.id
  role_definition_name = "Reader"
}

## Give yourself access to create key in Key Vault
resource "azurerm_key_vault_access_policy" "kv-access-policy-self" {
  key_vault_id = azurerm_key_vault.kv.id
  object_id = data.azurerm_client_config.current.object_id
  tenant_id = data.azurerm_client_config.current.tenant_id

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
  object_id = azurerm_disk_encryption_set.des.identity[0].principal_id
  tenant_id = data.azurerm_client_config.current.tenant_id

  key_permissions = [
    "get",
    "wrapkey",
    "unwrapkey",
  ]
} */
