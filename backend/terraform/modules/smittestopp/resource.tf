#
# Resources should be named according to conventions here:
# https://docs.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/naming-and-tagging
#

locals {
  full-domain            = "${var.name}.${var.domain}"
  name-suffix            = "${var.project}-${var.name}"
  namesuffix             = "${var.project}${var.name}"
  onboarding_service_url = "https://onboarding-aks.${local.full-domain}"
  fhi_service_url        = "https://fhi-aks.${local.full-domain}"
  tags = {
    Environment = var.name
  }
}


# Create a new resource group
resource "azurerm_resource_group" "rg" {
  name     = "rg-${local.name-suffix}"
  location = var.iothub_location
  # location = "northeurope" # hardcode for now to avoid destroying everything
}

# Networking

resource "azurerm_dns_zone" "dnszone" {
  name                = var.domain
  resource_group_name = azurerm_resource_group.rg.name
  count               = var.name == "prod" ? 1 : 0
}

resource "azurerm_dns_cname_record" "wildcards" {
  for_each            = toset(var.dns_wildcards)
  name                = "*.${each.value}"
  zone_name           = azurerm_dns_zone.dnszone[0].name
  resource_group_name = azurerm_resource_group.rg.name
  ttl                 = 300
  record              = "${each.value}.${var.domain}"
}

resource "azurerm_dns_caa_record" "caa" {
  for_each            = toset(var.dns_caa_subdomains)
  name                = each.value
  zone_name           = azurerm_dns_zone.dnszone[0].name
  resource_group_name = azurerm_resource_group.rg.name
  ttl                 = 300

  record {
    flags = 0
    tag   = "issue"
    value = "letsencrypt.org"
  }

  record {
    flags = 0
    tag   = "issuewild"
    value = "letsencrypt.org"
  }
}

resource "azurerm_dns_a_record" "subdomains" {
  for_each            = var.dns_a_records
  name                = each.key
  zone_name           = azurerm_dns_zone.dnszone[0].name
  resource_group_name = azurerm_resource_group.rg.name
  ttl                 = 300
  records             = [each.value]
}

# resource "azurerm_route_table" "aks" {
#   name                = "aks-routetable-${local.name-suffix}"
#   location            = azurerm_resource_group.rg.location
#   resource_group_name = azurerm_resource_group.rg.name
# }

# resource "azurerm_virtual_network" "vnet" {
#   name                = "vnet-${local.name-suffix}"
#   location            = azurerm_resource_group.rg.location
#   resource_group_name = azurerm_resource_group.rg.name
#   address_space       = ["10.0.0.0/8"]

#   tags = local.tags
# }

# resource "azurerm_subnet" "aks" {
#   name                 = "aks"
#   resource_group_name  = azurerm_resource_group.rg.name
#   virtual_network_name = azurerm_virtual_network.vnet.name
#   address_prefix       = "10.240.0.0/16"
# }

# resource "azurerm_subnet" "api" {
#   name                 = "api-management"
#   resource_group_name  = azurerm_resource_group.rg.name
#   virtual_network_name = azurerm_virtual_network.vnet.name
#   address_prefix       = "10.100.0.0/16"
# }

# resource "azurerm_subnet_route_table_association" "aks" {
#   subnet_id      = azurerm_subnet.aks.id
#   route_table_id = azurerm_route_table.aks.id
# }

# Storage

resource "azurerm_storage_account" "stor" {
  name                      = "st${local.namesuffix}"
  resource_group_name       = azurerm_resource_group.rg.name
  location                  = var.iothub_location
  account_tier              = "Standard"
  account_replication_type  = var.storage_replication_type
  account_kind              = "StorageV2"
  is_hns_enabled            = "true"
  enable_https_traffic_only = "true"
}

resource "azurerm_storage_container" "lake" {
  name                  = "dfs-${local.name-suffix}"
  storage_account_name  = azurerm_storage_account.stor.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "raw" {
  name                  = "dfs-${local.name-suffix}-raw"
  storage_account_name  = azurerm_storage_account.stor.name
  container_access_type = "private"
}

resource "azurerm_storage_account" "static" {
  name                      = "st${local.namesuffix}static"
  resource_group_name       = azurerm_resource_group.rg.name
  location                  = var.iothub_location
  account_tier              = "Standard"
  account_replication_type  = var.storage_replication_type
  account_kind              = "BlobStorage"
  enable_https_traffic_only = "true"
}

resource "azurerm_storage_container" "b2c" {
  name                  = "b2c"
  storage_account_name  = azurerm_storage_account.static.name
  container_access_type = "blob"
}

resource "azurerm_storage_blob" "b2c" {
  for_each               = setunion(fileset(path.module, "../../../b2c/templates/*.cshtml"), fileset(path.module, "../../../b2c/templates/*.css"))
  depends_on             = [azurerm_storage_container.b2c]
  name                   = basename(each.value)
  storage_account_name   = azurerm_storage_account.static.name
  storage_container_name = azurerm_storage_container.b2c.name
  # set content-type to text/css for .css
  content_type = "text/${reverse(split(".", each.value))[0]}"
  source_content = templatefile("${path.module}/${each.value}",
    {
      tenant_name          = var.tenant_name,
      storage_account_name = azurerm_storage_account.static.name
    }
  )
  type = "Block"
  # set cache-control header to force If-Modified-Since checks from the browser
  # ref: https://github.com/terraform-providers/terraform-provider-azurerm/issues/6236#issuecomment-604361019
  provisioner "local-exec" {
    command = "az storage blob update --account-name ${self.storage_account_name} --container-name ${self.storage_container_name} --name ${self.name} --content-cache-control 'no-cache, max-age=0'"
  }
}

resource "azurerm_storage_blob" "b2c-images" {
  for_each               = fileset(path.module, "../../../b2c/templates/images/*")
  depends_on             = [azurerm_storage_container.b2c]
  name                   = "images/${basename(each.value)}"
  storage_account_name   = azurerm_storage_account.static.name
  storage_container_name = azurerm_storage_container.b2c.name
  # set content-type to image/png for .png
  content_type = "image/${reverse(split(".", each.value))[0]}"
  source       = "${path.module}/${each.value}"
  type         = "Block"

  # set cache-control header to force If-Modified-Since checks from the browser
  # ref: https://github.com/terraform-providers/terraform-provider-azurerm/issues/6236#issuecomment-604361019
  provisioner "local-exec" {
    command = "az storage blob update --account-name ${self.storage_account_name} --container-name ${self.storage_container_name} --name ${self.name} --content-cache-control 'no-cache, max-age=0'"
  }
}



# Logging

resource "azurerm_log_analytics_workspace" "log" {
  for_each            = toset(["app", "aks", "backend"])
  name                = "log-${local.name-suffix}-${each.value}"
  location            = var.iothub_location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# Events

resource "azurerm_iothub" "iot" {
  name                = "iot-${local.name-suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.iothub_location
  tags                = local.tags
  # event_hub_retention_in_days = 7

  sku {
    name     = var.iothub_sku.name
    capacity = var.iothub_sku.capacity
  }

  lifecycle {
    ignore_changes = [
      # Ignore manual capacity changes
      sku[0].capacity,
    ]
  }

}

resource "azurerm_iothub_endpoint_storage_container" "raw-lake" {
  resource_group_name        = azurerm_resource_group.rg.name
  iothub_name                = azurerm_iothub.iot.name
  name                       = "raw-lake-json"
  container_name             = azurerm_storage_container.raw.name
  connection_string          = azurerm_storage_account.stor.primary_blob_connection_string
  batch_frequency_in_seconds = 600      # up-to 10 minute intervals
  max_chunk_size_in_bytes    = 10485760 # 10MB chunk limit
  encoding                   = "JSON"
  file_name_format           = "{iothub}-json/{YYYY}/{MM}/{DD}/{HH}/{YYYY}-{MM}-{DD}.{HH}-{mm}.{partition}.json"
}

resource "azurerm_iothub_route" "raw-lake-json" {
  resource_group_name = azurerm_resource_group.rg.name
  iothub_name         = azurerm_iothub.iot.name
  name                = "raw-lake-json"
  source              = "DeviceMessages"
  condition           = "true"
  endpoint_names      = [azurerm_iothub_endpoint_storage_container.raw-lake.name]
  enabled             = var.iothub_lake_enabled
}

resource "azurerm_iothub_route" "builtin" {
  resource_group_name = azurerm_resource_group.rg.name
  iothub_name         = azurerm_iothub.iot.name
  name                = "builtin-route"
  source              = "DeviceMessages"
  condition           = "true"
  endpoint_names      = ["events"]
  enabled             = true
}

resource "azurerm_iothub_dps" "dps" {
  name                = "iot-dps-${local.name-suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.iothub_location

  linked_hub {
    connection_string = "HostName=${azurerm_iothub.iot.hostname};SharedAccessKeyName=${azurerm_iothub.iot.shared_access_policy[0].key_name};SharedAccessKey=${azurerm_iothub.iot.shared_access_policy[0].primary_key}"
    location          = var.iothub_location
  }

  sku {
    name     = "S1"
    capacity = 1
  }
}

# resource "azurerm_stream_analytics_job" "test" {
#   name                = "asa-${local.name-suffix}-test"
#   resource_group_name = azurerm_resource_group.rg.name
# }

# resource "azurerm_stream_analytics_stream_input_iothub" "example" {
#   name                         = "example-iothub-input"
#   resource_group_name          = azurerm_resource_group.rg.name
#   stream_analytics_job_name    = azurerm_stream_analytics_job.test.name
#   endpoint                     = "messages/events"
#   eventhub_consumer_group_name = "$Default"
#   iothub_namespace             = azurerm_iothub.iot.name
#   shared_access_policy_key     = azurerm_iothub.iot.shared_access_policy[0].primary_key
#   shared_access_policy_name    = "iothubowner"

#   serialization {
#     type     = "Json"
#     encoding = "UTF8"
#   }
# }

# SQL

# resource "azurerm_sql_server" "sql" {
#   name                = "sqlserver-${local.name-suffix}"
#   resource_group_name = azurerm_resource_group.rg.name
#   location            = var.sql_location
#   # version                      = "12.0"
#   # administrator_login          = ""
#   # administrator_login_password = ""
# }

# resource "azurerm_storage_account" "auditing" {
#   name                     = "st${local.namesuffix}sqlaudit"
#   resource_group_name      = azurerm_resource_group.rg.name
#   location                 = azurerm_resource_group.rg.location
#   account_tier             = "Standard"
#   account_replication_type = var.storage_replication_type
# }

# resource "azurerm_sql_database" "example" {
#   name                = "sql01-${local.name-suffix}"
#   resource_group_name = azurerm_resource_group.rg.name
#   location            = var.sql_location
#   server_name         = azurerm_sql_server.sql.name

#   extended_auditing_policy {
#     storage_endpoint                        = azurerm_storage_account.audit.primary_blob_endpoint
#     storage_account_access_key              = azurerm_storage_account.audit.primary_access_key
#     storage_account_access_key_is_secondary = true
#     retention_in_days                       = 14
#   }

#   tags = local.tags
# }

# Containers


resource "azurerm_container_registry" "acr" {
  name                = "acr${local.namesuffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.iothub_location # not in norwayeast
  sku                 = "Standard"
  admin_enabled       = false
  tags                = local.tags
}


resource "azurerm_kubernetes_cluster" "aks" {
  name                            = "aks-${local.name-suffix}${var.aks_suffix}"
  location                        = var.location
  resource_group_name             = azurerm_resource_group.rg.name
  dns_prefix                      = "aks-${local.name-suffix}"
  api_server_authorized_ip_ranges = var.aks_authorized_ip_ranges

  network_profile {
    load_balancer_sku = "Standard"
    network_plugin    = "kubenet"
  }

  addon_profile {
    oms_agent {
      enabled                    = true
      log_analytics_workspace_id = azurerm_log_analytics_workspace.log["aks"].id
    }
  }

  role_based_access_control {
    enabled = true

    # Commented out because terraform wants to recreate the cluster when this was added
    # enabled AAD integration with the following command instead:
    # az aks update-credentials --resource-group <name of RG> --name <name of AKS cluster> --reset-aad --aad-server-app-id <appid> --aad-server-app-secret <secret> --aad-client-app-id <appid>
    # https://docs.microsoft.com/en-us/azure/aks/update-credentials#update-aks-cluster-with-new-aad-application-credentials
    #azure_active_directory {
    #  client_app_id     = var.aks_aadauth_client_app_id
    #  server_app_id     = var.aks_aadauth_server_app_id
    #  server_app_secret = var.aks_aadauth_server_app_secret
    #}
  }

  default_node_pool {
    name                = "default"
    node_count          = var.aks_default_node_pool.node_count
    vm_size             = var.aks_default_node_pool.vm_size
    enable_auto_scaling = var.aks_default_node_pool.enable_auto_scaling
    min_count           = var.aks_default_node_pool.min_count
    max_count           = var.aks_default_node_pool.max_count
    # vnet_subnet_id      = azurerm_subnet.aks.id
  }

  service_principal {
    # client_id     = azuread_application.aks.application_id
    # client_secret = random_string.aks-password.result
    client_id     = var.aks_client_id
    client_secret = var.aks_client_secret
  }

  tags = local.tags

  lifecycle {
    ignore_changes = [
      # Ignore changes to node count due to autoscaling
      default_node_pool[0].node_count,
      # rbac was deployed manually
      role_based_access_control,
    ]
  }
}

resource "azurerm_kubernetes_cluster_node_pool" "pool" {
  count                 = var.aks_node_pool.count
  name                  = "pool"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.aks.id
  vm_size               = var.aks_node_pool.vm_size
  enable_auto_scaling   = true
  min_count             = var.aks_node_pool.min_count
  max_count             = var.aks_node_pool.max_count
  node_count            = var.aks_node_pool.node_count

  lifecycle {
    ignore_changes = [
      # Ignore changes to node count due to autoscaling
      node_count,
    ]
  }
}

# Notification Hub

resource "azurerm_notification_hub_namespace" "nhubnamespace" {
  name                = "ntfns-${local.name-suffix}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
  namespace_type      = "NotificationHub"
  sku_name            = "Standard"
}

resource "azurerm_notification_hub" "nhub" {
  name                = "ntf-${local.name-suffix}"
  namespace_name      = azurerm_notification_hub_namespace.nhubnamespace.name
  resource_group_name = azurerm_resource_group.rg.name
  location            = var.location
}

# API Management in front of AKS endpoints

resource "azurerm_api_management" "api" {
  # no modifications to this resource!!!
  # it gets kicked off the vnet on every update
  name                = "api-${local.name-suffix}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  publisher_name      = ""
  publisher_email     = ""

  sku_name = var.api_management_sku

  # don't add policy here,
  # add it manually via portal
  # policy {
  #   xml_content = file("${path.module}/global-policy.xml")
  # }
}

resource "azurerm_api_management_backend" "onboarding" {
  name                = "device-onboarding"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  protocol            = "http"
  url                 = local.onboarding_service_url
  tls {
    validate_certificate_chain = false
    validate_certificate_name  = false
  }
}

resource "azurerm_api_management_api" "onboarding" {
  name                = "device-onboarding"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  revision            = "1"
  display_name        = "Device Registration"
  path                = "onboarding"
  protocols           = ["http", "https"]
  service_url         = local.onboarding_service_url
}

resource "azurerm_api_management_api_operation" "register-device" {
  operation_id        = "register-device"
  api_name            = azurerm_api_management_api.onboarding.name
  api_management_name = azurerm_api_management_api.onboarding.api_management_name
  resource_group_name = azurerm_api_management_api.onboarding.resource_group_name
  display_name        = "Register Device"
  method              = "POST"
  url_template        = "/register-device"
  description         = "Register a device"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api" "permissions" {
  name                = "permissions"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  revision            = "1"
  display_name        = "Permissions Management"
  path                = "permissions"
  protocols           = ["http", "https"]
  service_url         = local.onboarding_service_url
}

resource "azurerm_api_management_api_operation" "revoke-consent" {
  operation_id        = "revoke-consent"
  api_name            = azurerm_api_management_api.permissions.name
  api_management_name = azurerm_api_management_api.permissions.api_management_name
  resource_group_name = azurerm_api_management_api.permissions.resource_group_name
  display_name        = "Revoke Consent"
  method              = "POST"
  url_template        = "/revoke-consent"
  description         = "Revoke data collection consent"

  response {
    status_code = 200
  }
}


# validate jwt tokens at the API Management level
resource "azurerm_api_management_api_policy" "jwt" {
  for_each            = { for api in [azurerm_api_management_api.onboarding, azurerm_api_management_api.permissions] : api.name => api }
  api_name            = each.key
  api_management_name = each.value.api_management_name
  resource_group_name = each.value.resource_group_name

  xml_content = templatefile("${path.module}/backend-policy.xml", {
    backend_client_id = var.backend_client_id,
    tenant_id         = var.tenant_id,
    tenant_name       = var.tenant_name,
  })
}

# Device-authenticated app endpoints

resource "azurerm_api_management_api" "app" {
  name                = "app"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  revision            = "1"
  display_name        = "IoTHub-authenticated requests from the app"
  path                = "app"
  protocols           = ["http", "https"]
  service_url         = local.onboarding_service_url
}

resource "azurerm_api_management_api_operation" "pin" {
  operation_id        = "pin"
  api_name            = azurerm_api_management_api.app.name
  api_management_name = azurerm_api_management_api.app.api_management_name
  resource_group_name = azurerm_api_management_api.app.resource_group_name
  display_name        = "Request PIN"
  method              = "GET"
  url_template        = "/pin"
  description         = "Request App PINs"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_operation" "contactids" {
  operation_id        = "contactids"
  api_name            = azurerm_api_management_api.app.name
  api_management_name = azurerm_api_management_api.app.api_management_name
  resource_group_name = azurerm_api_management_api.app.resource_group_name
  display_name        = "Request a new pool of proximity contact ids"
  method              = "POST"
  url_template        = "/contactids"
  description         = "Request new contact ids"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_product" "app" {
  product_id            = "app"
  resource_group_name   = azurerm_resource_group.rg.name
  api_management_name   = azurerm_api_management.api.name
  display_name          = "app"
  subscription_required = false
  approval_required     = false
  published             = true
}

resource "azurerm_api_management_product_api" "app" {
  for_each = toset(
    [
      "device-onboarding",
      "permissions",
      "app",
    ]
  )
  api_name            = each.value
  product_id          = azurerm_api_management_product.app.product_id
  api_management_name = azurerm_api_management.api.name
  resource_group_name = azurerm_api_management.api.resource_group_name
}

# FHI API endpoints

resource "azurerm_api_management_backend" "fhi" {
  name                = "fhi"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  protocol            = "http"
  url                 = local.fhi_service_url

  tls {
    validate_certificate_chain = false
    validate_certificate_name  = false
  }
}

resource "azurerm_api_management_certificate" "fhi-test-client" {
  name                = "fhi-test-client"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  data                = filebase64(var.fhi_client_cert)
  count               = var.enable_fhi_test_certificate ? 1 : 0
}

resource "azurerm_api_management_api" "fhi" {
  name                = "fhi"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  revision            = "1"
  display_name        = "FHI"
  path                = "fhi"
  protocols           = ["http", "https"]
  service_url         = local.fhi_service_url
}

resource "azurerm_api_management_api_operation" "lookup" {
  operation_id        = "lookup"
  api_name            = azurerm_api_management_api.fhi.name
  api_management_name = azurerm_api_management_api.fhi.api_management_name
  resource_group_name = azurerm_api_management_api.fhi.resource_group_name
  display_name        = "Lookup a phone"
  method              = "POST"
  url_template        = "/lookup"
  description         = "Lookup a phone"

  response {
    status_code = 202
    description = "the request id and the url for retrieving the result as JSON"
    representation {
      content_type = "application/json"
      sample = jsonencode(
        {
          request_id = "u-u-i-d",
          result_url = "https://api-host/lookup/{request_id}",
        }
      )
    }
  }
}

resource "azurerm_api_management_api_operation" "lookup-result" {
  operation_id        = "lookup-result"
  api_name            = azurerm_api_management_api.fhi.name
  api_management_name = azurerm_api_management_api.fhi.api_management_name
  resource_group_name = azurerm_api_management_api.fhi.resource_group_name
  display_name        = "Lookup Result"
  method              = "GET"
  url_template        = "/lookup/{request_id}"
  description         = "Retrieve the result of a lookup request"

  template_parameter {
    name        = "request_id"
    required    = true
    type        = "string"
    description = "the request id whose result is being retrieved"
  }
  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_operation" "deletions" {
  operation_id        = "deletions"
  api_name            = azurerm_api_management_api.fhi.name
  api_management_name = azurerm_api_management_api.fhi.api_management_name
  resource_group_name = azurerm_api_management_api.fhi.resource_group_name
  display_name        = "Lookup deleted numbers"
  method              = "POST"
  url_template        = "/deletions"
  description         = "Check the presence of numbers in the system"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_operation" "fhi-egress" {
  operation_id        = "fhi-egress"
  api_name            = azurerm_api_management_api.fhi.name
  api_management_name = azurerm_api_management_api.fhi.api_management_name
  resource_group_name = azurerm_api_management_api.fhi.resource_group_name
  display_name        = "Data egress (FHI)"
  method              = "POST"
  url_template        = "/fhi-egress"
  description         = "Egress API for FHI"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_operation" "fhi-access" {
  operation_id        = "fhi-access"
  api_name            = azurerm_api_management_api.fhi.name
  api_management_name = azurerm_api_management_api.fhi.api_management_name
  resource_group_name = azurerm_api_management_api.fhi.resource_group_name
  display_name        = "Access log (FHI)"
  method              = "POST"
  url_template        = "/fhi-access-log"
  description         = "Get the access log via FHI"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_policy" "fhi" {
  for_each            = { for api in [azurerm_api_management_api.fhi] : api.name => api }
  api_name            = each.key
  api_management_name = each.value.api_management_name
  resource_group_name = each.value.resource_group_name
  depends_on          = [azurerm_api_management_certificate.fhi-test-client]

  xml_content = templatefile(
    "${path.module}/fhi-policy.xml",
    {
      allowed_ips            = var.fhi_ips,
      backend_password       = var.fhi_backend_password,
      client_cert_thumbprint = var.fhi_client_cert_thumbprint,
    }
  )
}

resource "azurerm_api_management_product" "fhi" {
  product_id            = "fhi"
  resource_group_name   = azurerm_resource_group.rg.name
  api_management_name   = azurerm_api_management.api.name
  display_name          = "FHI"
  subscription_required = false
  approval_required     = false
  published             = true
}

resource "azurerm_api_management_product_api" "app-fhi" {
  api_name            = azurerm_api_management_api.fhi.name
  product_id          = azurerm_api_management_product.fhi.product_id
  api_management_name = azurerm_api_management.api.name
  resource_group_name = azurerm_api_management.api.resource_group_name
}

# Helse Norge API endpoints

resource "azurerm_api_management_backend" "helsenorge" {
  name                = "helsenorge"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  protocol            = "http"
  url                 = local.fhi_service_url
}

resource "azurerm_api_management_api" "helsenorge" {
  name                = "helsenorge"
  resource_group_name = azurerm_resource_group.rg.name
  api_management_name = azurerm_api_management.api.name
  revision            = "1"
  display_name        = "Helse Norge"
  path                = "helsenorge"
  protocols           = ["http", "https"]
  service_url         = local.fhi_service_url
}

resource "azurerm_api_management_api_operation" "egress" {
  operation_id        = "egress"
  api_name            = azurerm_api_management_api.helsenorge.name
  api_management_name = azurerm_api_management_api.helsenorge.api_management_name
  resource_group_name = azurerm_api_management_api.helsenorge.resource_group_name
  display_name        = "Egress"
  method              = "POST"
  url_template        = "/egress"
  description         = "Retrieve stored data"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_operation" "access" {
  operation_id        = "access-log"
  api_name            = azurerm_api_management_api.helsenorge.name
  api_management_name = azurerm_api_management_api.helsenorge.api_management_name
  resource_group_name = azurerm_api_management_api.helsenorge.resource_group_name
  display_name        = "Access Log"
  method              = "POST"
  url_template        = "/access-log"
  description         = "Retrieve access log"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_operation" "hn-revoke-consent" {
  operation_id        = "revoke-consent"
  api_name            = azurerm_api_management_api.helsenorge.name
  api_management_name = azurerm_api_management_api.helsenorge.api_management_name
  resource_group_name = azurerm_api_management_api.helsenorge.resource_group_name
  display_name        = "Revoke Consent"
  method              = "POST"
  url_template        = "/revoke-consent"
  description         = "Revoke consent and delete data"

  response {
    status_code = 200
  }
}

resource "azurerm_api_management_api_policy" "helsenorge" {
  for_each            = { for api in [azurerm_api_management_api.helsenorge] : api.name => api }
  api_name            = each.key
  api_management_name = each.value.api_management_name
  resource_group_name = each.value.resource_group_name

  xml_content = templatefile(
    "${path.module}/helsenorge-policy.xml",
    {
      allowed_ips            = var.helsenorge_ips,
      backend_password       = var.fhi_backend_password,
      client_cert_thumbprint = var.helsenorge_client_cert_thumbprint,
      openid_config_url      = var.helsenorge_openid_config_url,
    }
  )
}

resource "azurerm_api_management_product" "helsenorge" {
  product_id            = "helsenorge"
  resource_group_name   = azurerm_resource_group.rg.name
  api_management_name   = azurerm_api_management.api.name
  display_name          = "Helse Norge"
  subscription_required = false
  approval_required     = false
  published             = true
}

resource "azurerm_api_management_product_api" "app-helsenorge" {
  api_name            = azurerm_api_management_api.helsenorge.name
  product_id          = azurerm_api_management_product.helsenorge.product_id
  api_management_name = azurerm_api_management.api.name
  resource_group_name = azurerm_api_management.api.resource_group_name
}
