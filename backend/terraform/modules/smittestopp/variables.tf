variable "location" {
  type        = string
  description = "zone"
  default     = "northeurope"
}

variable "iothub_location" {
  type        = string
  description = "zone"
  default     = "northeurope"
}

variable "project" {
  type        = string
  description = "project name"
  default     = "smittestopp"
}

variable "name" {
  type        = string
  description = "name of the deployment"
  default     = "dev"
}

variable "tenant_name" {
  type        = string
  description = "name of the AAD B2C tenant"
}

variable "tenant_id" {
  type        = string
  description = "id of the AAD B2C tenant"
}

variable "backend_client_id" {
  type        = string
  description = "id of the AAD B2C backend application"
}

variable "domain" {
  type        = string
  description = "domain under which we will be deployed"
  default     = "corona.nntb.no"
}

variable "dns_caa_subdomains" {
  type        = list(string)
  description = "list of domains for CAA records"
  default     = []
}

variable "dns_wildcards" {
  type        = list(string)
  description = "list of subdomains to add *.subdomain records for"
  default     = []
}

variable "dns_a_records" {
  type        = map
  description = "map of subdomain:ip for A records"
  default     = {}
}

variable "storage_replication_type" {
  type        = string
  description = "replication type for storage account"
  default     = "LRS"
}

variable "iothub_sku" {
  type        = map
  description = "SKU for IoTHub"
  default = {
    name     = "S1"
    capacity = "1"
  }
}

variable "iothub_lake_enabled" {
  type        = bool
  description = "Enable IoTHub datalake import"
  default     = true
}

variable "aks_default_node_pool" {
  type        = map
  description = "AKS default node pool variables"
  default = {
    node_count          = 1
    vm_size             = "Standard_D2_v3"
    min_count           = 1
    max_count           = 10
    enable_auto_scaling = true
  }
}

variable "aks_node_pool" {
  type        = map
  description = "AKS extra node pool variables"
  default = {
    count               = 0
    node_count          = 1
    vm_size             = "Standard_D16_v3"
    min_count           = 1
    max_count           = 10
    enable_auto_scaling = true
  }
}

variable "api_management_sku" {
  type        = string
  description = "sku name for api management"
  default     = "Developer_1"
}

variable "aks_client_id" {
  type        = string
  description = "client id of service principal for AKS"
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "aks_client_secret" {
  type        = string
  description = "client secret of service principal for AKS"
  default     = "00000000000000000000000000000000"
}

variable "aks_aadauth_client_app_id" {
  type        = string
  description = "Azure AD Client App ID. Details: https://docs.microsoft.com/en-us/azure/aks/azure-ad-integration"
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "aks_aadauth_server_app_id" {
  type        = string
  description = "Azure AD Server App ID. Details: https://docs.microsoft.com/en-us/azure/aks/azure-ad-integration"
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "aks_aadauth_server_app_secret" {
  type        = string
  description = "Azure AD Server Secret. Details: https://docs.microsoft.com/en-us/azure/aks/azure-ad-integration"
  default     = "00000000000000000000000000000000"
}

variable "aks_authorized_ip_ranges" {
  type        = list(string)
  description = "list of authorized ip ranges"
  default     = []
}

variable "aks_suffix" {
  type        = string
  description = "suffix, if any, for aks cluster (allows create before delete)"
  default     = ""
}

variable "fhi_client_cert" {
  type        = string
  description = "path to fhi client ssl certificate (as .pfx)"
  default     = "secrets/client-cert.pfx"
}

variable "fhi_client_cert_thumbprint" {
  type        = string
  description = "thumbprint of fhi client cert"
}

variable "fhi_client_ca" {
  type        = string
  description = "path to fhi client ssl CA (as .pfx)"
  default     = "secrets/client-ca.pfx"
}

variable "fhi_backend_password" {
  type        = string
  description = "Basic auth password for FHI backend"
}

variable "fhi_ips" {
  type        = list(string)
  description = "list of ips to allow"
  default     = []
}

variable "enable_fhi_test_certificate" {
  type        = bool
  description = "Whether to enable a client certificate for the FHI endpoint for testing"
  default     = false
}

variable "helsenorge_client_cert_thumbprint" {
  type        = string
  description = "thumbprint of hn client cert"
}

variable "helsenorge_ips" {
  type        = list(string)
  description = "list of ips to allow"
  default     = []
}

variable "helsenorge_openid_config_url" {
  type        = string
  description = "OpenID config url (typically ends v2[.0]/.well-known/openid-config)"
}
