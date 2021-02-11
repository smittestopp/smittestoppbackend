# Smittestopp backend architecture

## HTTP endpoints
All HTTP endpoints are managed in Azure APIM which is configured via Terraform.
 
The details of the authentication processes varies with the endpoints that are called by the different clients, which are:
- Mobile App
- FHI
- helsenorge.no

The mobile app endpoints are behind a Web Application Firewall (WAF), whereas the FHI and helsenorge.no 
endpoints are accessed directly in APIM (due to a lack of support for SSL client auth in WAF).

A service prefix is added in API Management (APIM), e.g. `/fhi` or `/onboarding`.

## Kubernetes deployments

The backend consists of four dockerized services that are deployed to Azure Kubernetes Service (AKS).
- Analysis
- Corona
- Delete
- FHI

#### Corona

The _corona_ service handles device registration and consent revocation requests from the app users. 
In addition, this image also contains clients for communicating with the following external services:

- Microsoft Graph API (access point for information about Azure AD users).
- Azure IOT-Hub (access point for information about devices).
- SQL Database (where GPS location and bluetooth contact events are stored).

#### FHI

The _FHI_ service handles requests from FHI and helsenorge.no. 

It uses redis to queue analysis jobs that are processed by the analysis image when 
requested by FHI.

#### Analysis

The _analysis_ service is responsible of calculating potential contacts between a person infected 
with the corona virus and other app users over timespan requested from Folkehelseinstituttet (FHI).  

The analysis service has no publicly exposed endpoints, but it communicates with the corona service through 
read and writes to a redis database.

#### Delete

The _delete_ service is responsible for deleting which is "old" or associated with users that have 
revoked their consents. Details about the deletion service and data storage rules are explained in DELETION.md)

## Registration and contact tracing

#### User registration

User profiles and corresponding devices are managed by Azure AD B2C and Azure IOTHub, respectively.
Users are onboarded by registering their phone number and authenticating their identities with B2C Login in the app. 

#### Contact tracing

1. FHI makes a call to the _lookup_ _phone_ _number_ endpoint with the phone number of a person that has tested positive
for the corona virus.  
2. From the request an analysis job is scheduled as a record in a redis database (description below).
3. A link to a endpoint for receiving the result is returned to the caller. FHI calls this endpoint until
they receive response 200.  
4. A "worker job" in the analysis picks jobs from the queue and performs a contact analysis. 
5. When the analysis job is complete the result is stored in a json format on the redis object under the key "result".
6. The analysis report is returned to FHI (ref. step 3). From the report FHI can contact people who are likely to have 
been in contact with the infected person during the period specified in the request. 

This service does not not have any publicly exposed endpoints.

## Repo layout in /backend

- images (build our docker images)
- terraform (deploy Azure resources, infrequent update)
- helm (deploy our services, frequent update)
- helm/admin (deploy our AKS permissions)
- b2c (auth configuration)
- test (integration and performance tests for running against a full deployment)
- secrets (some credentials, ssl certificates)
- Makefile (automation of common tasks)

## SSL certificates

We have SSL certificates for `[dev|prod].corona.nntb.no` issued via letsencrypt.
These are verified with DNS using the Azure DNS [zone for corona.nntb.no](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-prod/providers/Microsoft.Network/dnszones/corona.nntb.no/overview).

These certificates are used in:

- helm/secrets for SSL verification of AKS endpoints
- key vaults for the public API endpoints:
  - [prod](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-prod/providers/Microsoft.KeyVault/vaults/kv-smittestopp-prod/certificates)
  - [dev](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-dev/providers/Microsoft.KeyVault/vaults/kv-smittestopp-dev/certificates)

Upload to key vaults is manual via the Azure portal.
They are stored in both PEM and PFX formats in the key vaults,
though only PFX is used, currently.
PFX files have empty passphrases.
PFX files are in `secrets/letsencrypt/$(RELEASE).pfx`.

To issue new certificates, run:

    make ssl-request RELEASE=dev # or prod
    
The first time you run this, the make command will fail but prints a certbot command that needs to be run.
It will guide you through the process of creating records in the Azure DNS zone for corona.nntb.no.
After the cerbot job has finished run the make command again.

Now you have the new certificates on you local disk. Add them to helm in `helm/secrets/$RELEASE.yaml`:

- `tls.key` is `privkey.pem`
- `tls.cert` is `fullchain.pem`

To publish your changes to the k8s cluster use:

    make helm-diff # just to see the changes
    make helm-upgrade

The changes also need to be merged to the main branch, so please create a PR.

To upload the PFX files to the key vaults, go to:

- [dev pfx in key vault](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-dev/providers/Microsoft.KeyVault/vaults/kv-smittestopp-dev/certificates)
- [prod pfx in key vault](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-prod/providers/Microsoft.KeyVault/vaults/kv-smittestopp-prod/certificates)

1. select "New Version"
2. Method: Import
3. Upload `secrets/letsencrypt/$RELEASE.pfx`
4. Empty passphrase

To add the certificates the Application gateway listeners:

- [dev](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-dev/providers/Microsoft.Network/applicationGateways/waf-smittestopp-pub-dev/listeners)
- [prod](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-waf-prod/providers/Microsoft.Network/applicationGateways/waf-smittestopp-pub-prod/listeners)

:warning: The integration of Azure Key Vault into Application Gateway is broken (see https://github.com/MicrosoftDocs/azure-docs/issues/33157).
The Key Vault firewall needs to be disabled, so that the Application Gateway can get the new certificate.
- [dev](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-dev/providers/Microsoft.KeyVault/vaults/kv-smittestopp-dev/networking)
- [prod](https://portal.azure.com/#@fhi.no/resource/subscriptions/<subscription_id>/resourceGroups/rg-smittestopp-prod/providers/Microsoft.KeyVault/vaults/kv-smittestopp-prod/networking)

To keep the whitelist, it is recommended to take a copy before allowing access from all networks.
It worked though to have one tab open with the firewall settings and another one to follow the Application Gateway procedure below.
Then the whitelist stays the same after switching allowed access back to only private endpoints and selected networks.

To update the certificate for the public api:

1. select the pubapi Listener (there's only one)
2. check "Renew or edit selected certificate"
3. select "Choose a certificate from Key Vault"
4. select the key vault and PFX certificate that you uploaded previously
5. Save
6. verify by checking the SSL certificate expiry at https://pubapi.$RELEASE.corona.nntb.no

:warning: Remember to switch the firewall back on (see above)!

This must be done every 60-90 days.

## B2C

User accounts live in Azure Active Directory B2C,
a different tenant from the main deployment for each of dev and prod.
This is where we record phone numbers (as users) and device ids (as groups)
and their relationships (group membership).

The B2C HTML templates live in b2c/templates and are uploaded with terraform.

The B2C custom policy files, which specify how apps can be authenticated
are uploaded via the Azure B2C "Identity Experience Framework".
The policy files are different for dev and prod (only in some URLs and tenant ids) and are uploaded via the "Upload custom policy" link on the Identify Experience Framework page ([link for dev](https://portal.azure.com/#blade/Microsoft_AAD_B2CAdmin/CustomPoliciesMenuBlade/overview/tenantId/devsmittestopp.onmicrosoft.com)).

Login is disabled in prod by uploading b2c/prod/disabled.xml.
Login can be re-enabled by uploading b2c/prod/phone-signup-signin.xml.
Both files define the `B2C_1A_phone_SUSI` policy used by apps.
The `disabled.xml` in dev specifies a *different* policy id,
so it can be used for testing in dev without disabling dev registration.





