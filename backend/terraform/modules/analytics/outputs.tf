output "rg-name" {
  value = azurerm_resource_group.rg.name
}

output "des-id" {
  value = azurerm_disk_encryption_set.des.id
}

output "vnet-id" {
  value = azurerm_virtual_network.vnet.id
}

output "vnet-name" {
  value = azurerm_virtual_network.vnet.name
}

/*
output "rg-id" {
  value = azurerm_resource_group.rg.id
}

output "vnet-name" {
  value = azurerm_virtual_network.vnet.name
}

output "des" {
  value = azurerm_disk_encryption_set.des
}

output "snet-analytics-address-prefix" {
  value = azurerm_subnet.snet-vm.address_prefix
}

output "snet-bastion-address-prefix" {
  value = azurerm_subnet.snet-bastion.address_prefix
}*/