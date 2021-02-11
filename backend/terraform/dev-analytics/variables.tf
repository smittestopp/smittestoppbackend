# Basics
variable "subscription_id" {
  type        = string
  description = "subscription where we will be deployed"
  default     = ""
}

variable "vm-win-jumphost-admin-pw" {
  type        = string
  description = "Admin pw"
}