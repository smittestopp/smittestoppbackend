# Configure the Azure provider
provider "azurerm" {
  version         = "~>1.41.0"
  subscription_id = var.subscription_id
  # features {}
}

provider "random" {
  version = "~>2.2"
}

# Configure the Azure storage backend
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-smittestopp-tfstate-dev"
    storage_account_name = "stsmittestopptfstatedev"
    container_name       = "tfstate"
    key                  = "dev.terraform.tfstate"
  }
}

# Call the module
module "smittestopp" {
  source = "../modules/smittestopp"

  # dev-secrets.tfvars
  name                              = "dev"
  tenant_name                       = "devsmittestopp"
  tenant_id                         = ""
  backend_client_id                 = ""
  fhi_client_cert                   = "${path.root}/secrets/client-cert.pfx"
  fhi_client_cert_thumbprint        = var.fhi_client_cert_thumbprint
  fhi_backend_password              = var.fhi_backend_password
  fhi_ips                           = var.fhi_ips
  helsenorge_client_cert_thumbprint = var.helsenorge_client_cert_thumbprint
  helsenorge_ips                    = var.helsenorge_ips
  helsenorge_openid_config_url      = "https://eksternapi.hn.test.nhn.no/sts/helsenorge-oidc-provider/v2/.well-known/openid-configuration"
  enable_fhi_test_certificate       = true

  aks_authorized_ip_ranges = concat(
    [
      "", # Host1
      ""  # Host2
     ],
    jsondecode(file("${path.root}/../azureips.json"))
  )

  aks_suffix = "-1"

  # Commented out because terraform wants to recreate the cluster when this was added
  # enabled AAD integration with the following command instead:
  # az aks update-credentials --resource-group <name of RG> --name <name of AKS cluster> --reset-aad --aad-server-app-id <appid> --aad-server-app-secret <secret> --aad-client-app-id <appid>
  # https://docs.microsoft.com/en-us/azure/aks/update-credentials#update-aks-cluster-with-new-aad-application-credentials
  #aks_aadauth_client_app_id = "" # FHI-Smittestopp-AKS-AzureAD-Client
  #aks_aadauth_server_app_id = "" # FHI-Smittestopp-AKS-AzureAD-Server
  #aks_aadauth_server_app_secret = var.aks_aadauth_server_app_secret

  aks_client_id     = var.aks_client_id_dev
  aks_client_secret = var.aks_client_secret_dev
}

# Do anything directly with kubernetes? Currently CRDs, helm are separate commands
provider "kubernetes" {
  version = "~>1.11"

  load_config_file = "false"

  host               = module.smittestopp.kube_config-host
  client_certificate = module.smittestopp.kube_config-client_certificate
  client_key         = module.smittestopp.kube_config-client_key
}

output "kube_config" {
  value     = module.smittestopp.kube_config
  sensitive = true
}
