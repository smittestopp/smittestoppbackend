variable "subscription_id" {
  type        = string
  description = "subscription where we will be deployed"
  default     = ""
}

variable "aks_client_id_dev" {
  type        = string
  description = "client id of service principal for AKS"
  default     = "00000000-0000-0000-0000-000000000000"
}

variable "aks_client_secret_dev" {
  type        = string
  description = "client secret of service principal for AKS"
  default     = "00000000000000000000000000000000"
}

variable "fhi_client_cert_thumbprint" {
  type        = string
  description = "thumbprint of client cert"
}

variable "fhi_backend_password" {
  type        = string
  description = "Basic auth password for FHI backend"
}

variable "fhi_ips" {
  type        = list(string)
  description = "list of ips to allow for fhi endpoints"
  default     = []
}

variable "helsenorge_client_cert_thumbprint" {
  type        = string
  description = "thumbprint of hn client cert"
}

variable "helsenorge_ips" {
  type        = list(string)
  description = "list of ips to allow for helsenorge endpoints"
  default     = []
}

# variable "aks_aadauth_server_app_secret" {
#   type = string
#   description = "Azure AD Server Secret. Details: https://docs.microsoft.com/en-us/azure/aks/azure-ad-integration"
# }
