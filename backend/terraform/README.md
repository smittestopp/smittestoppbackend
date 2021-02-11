# Terraform

## Backend configuration
Azure Storage blob is used as a backend for the tfstate files. We have a blob in each subscription holding the tfstate file. Because of that, we have to change the subscription we're working against for each environment.

Before running `terraform plan` and `terraform apply` you need to change the context:
* Dev environment: `az account set -s "b0a2db0c-ef6e-49ac-8e53-798ad3a81003"`
* Prod environment: `az account set -s "b13feaad-eef3-4d99-8a13-67c0c62696ea"`

## Secrets and variables
When tfvars files is placed in a subfolder, like we do with the secrets, we need to specify the var-file when running `terraform plan` and `terraform apply`.
* Dev environment:
    1. `terraform plan -var-file ./secrets/dev-secrets.tfvars`
    2. `terraform apply -var-file ./secrets/dev-secrets.tfvars`
* Prod environment:
    1. `terraform plan -var-file ./secrets/prod-secrets.tfvars`
    2. `terraform apply -var-file ./secrets/prod-secrets.tfvars`
