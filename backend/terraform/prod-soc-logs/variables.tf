# Basics
variable "subscription_id" {
  type        = string
  description = "subscription where we will be deployed"
  default     = ""
}

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

# Storage
variable "storage-suffix" {
  type = string
  description = "Naming suffix of storage account"
}

variable "storage-replication-type" {
  type = string
  description = "Defines the type of replication to use for this storage account. Valid options are LRS, GRS, RAGRS and ZRS"
  default = "LRS"
}

variable "storage-account-tier" {
  type = string
  description = "Valid options are Standard and Premium. For FileStorage accounts only Premium is valid."
  default = "Standard"
}

variable "storage-account-kind" {
  type = string
  description = "Valid options are BlobStorage, BlockBlobStorage, FileStorage, Storage and StorageV2"
  default = "StorageV2"
}

variable "storage-access-tier" {
  type = string
  description = "Defines the type of replication to use for this storage account. Valid options are LRS, GRS, RAGRS and ZRS."
  default = "Hot"
}

variable "storage-network-rules-default-action" {
  type = string
  description = "Specifies the default action of allow or deny when no other rules match. Valid options are Deny or Allow."
  default = "Deny"
}

variable "storage-network-rules-ip-rules" {
  type = list(string)
  description = "List of public IP or IP ranges in CIDR Format. Only IPV4 addresses are allowed."
}
