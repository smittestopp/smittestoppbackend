output "app-log-key" {
  value     = azurerm_log_analytics_workspace.log["app"].primary_shared_key
  sensitive = true
}

output "storage-url" {
  value = azurerm_storage_account.stor.primary_dfs_endpoint
}

output "storage_access_key" {
  value     = azurerm_storage_account.stor.primary_access_key
  sensitive = true
}

output "kube_config" {
  value     = azurerm_kubernetes_cluster.aks.kube_config_raw
  sensitive = true
}

output "kube_config-host" {
  value = azurerm_kubernetes_cluster.aks.kube_config.0.host
}

output "kube_config-client_certificate" {
  value = azurerm_kubernetes_cluster.aks.kube_config.0.client_certificate
  sensitive = true
}

output "kube_config-client_key" {
  value = azurerm_kubernetes_cluster.aks.kube_config.0.client_key
  sensitive = true
}