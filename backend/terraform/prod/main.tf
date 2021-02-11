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
    resource_group_name  = "rg-smittestopp-tfstate-prod"
    storage_account_name = "stsmittestopptfstateprod"
    container_name       = "tfstate"
    key                  = "prod.terraform.tfstate"
  }
}

# Call the module
module "smittestopp" {
  source = "../modules/smittestopp"

  # prod-secrets.tfvars
  name                              = "prod"
  tenant_name                       = "smittestopp"
  tenant_id                         = ""
  backend_client_id                 = ""
  fhi_client_cert                   = "${path.root}/secrets/client-cert.pfx"
  fhi_client_cert_thumbprint        = var.fhi_client_cert_thumbprint
  fhi_backend_password              = var.fhi_backend_password
  fhi_ips                           = var.fhi_ips
  helsenorge_client_cert_thumbprint = var.helsenorge_client_cert_thumbprint
  helsenorge_ips                    = var.helsenorge_ips
  helsenorge_openid_config_url      = "https://eksternapi.helsenorge.no/sts/helsenorge-oidc-provider/v2/.well-known/openid-configuration"

  dns_caa_subdomains = ["dev", "prod"]
  dns_wildcards      = []
  dns_a_records = {
    "ci.dev" : "",
    "fhi-aks.dev" : "",
    "onboarding-aks.dev" : "",
    "fhi-aks.prod" : "",
    "onboarding-aks.prod" : "",
  }

  location        = "northeurope"
  iothub_location = "northeurope"

  iothub_sku = {
    name     = "S1"
    capacity = "1"
  }
  iothub_lake_enabled = false

  aks_default_node_pool = {
    node_count          = 1
    vm_size             = "Standard_F8s_v2"
    min_count           = 1
    max_count           = 1
    enable_auto_scaling = true
  }

  aks_node_pool = {
    count               = 0
    node_count          = 1
    vm_size             = "Standard_F16s_v2"
    min_count           = 1
    max_count           = 1
    enable_auto_scaling = true
  }

  aks_authorized_ip_ranges = [
    "1.2.3.4/32", # Host1
    "",  # Host2
  ]

  aks_suffix = "-north"

  # AKS Azure AD integration
  # Commented out because terraform wants to recreate the cluster when this was added
  # enabled AAD integration with the following command instead:
  # az aks update-credentials --resource-group rg-smittestopp-dev --name aks-smittestopp-dev-1 --reset-aad --aad-server-app-id <appid> --aad-server-app-secret <secret> --aad-client-app-id <appid>
  # https://docs.microsoft.com/en-us/azure/aks/update-credentials#update-aks-cluster-with-new-aad-application-credentials
  #aks_aadauth_client_app_id     = "" # FHI-Smittestopp-AKS-AzureAD-Client
  #aks_aadauth_server_app_id     = "" # FHI-Smittestopp-AKS-AzureAD-Server
  #aks_aadauth_server_app_secret = var.aks_aadauth_server_app_secret

  # can only use developer or premium to get access to vnet
  api_management_sku = "Premium_1"

  aks_client_id     = var.aks_client_id_prod
  aks_client_secret = var.aks_client_secret_prod
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
