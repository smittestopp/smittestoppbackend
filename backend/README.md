# Overview

Azure resources are deployed with terraform.
Additionally, some services are deployed to AKS via helm (must be helm v3).

## Deploying

1. get things started with `make terraform` (`make terraform RELEASE=prod` for production)
2. first-time manual steps:
   1. add API management to AKS vnet:
      1. (on Virtual Network aks-vnet...) create new subnet:
         1. Settings > Subnets, pick `+ Subnet`
         2. name = `api-management`
         3. address range = `10.100.0.0/24`
      2. (on API management) Settings > Virtual Network; pick External
         1. For virtual Network, pick aks-vnet-...
         2. For subnet, pick api-management
   2. deploy cert-manager CRDs to AKS:
      1. `make crds` (`make crds RELEASE=prod`)
   3. Create symmetric key enrollment group in `iot-dps-smittestopp-$RELEASE` and note the primary key
   4. delete and re-add linked iothub in device provisioning service (not sure why this is necessary, but apparently the link created by terraform doesn't work).

# Applying updates

To apply updates:

changed resources: `make terraform`

Updating images: `make build` and/or `make push` to update images.
If only images are changed, use `kubectl delete pod` to just restart services.

If configuration is changed, use `make helm-upgrade`

# Requesting a token to talk to the API:

Visit [this link](https://devsmittestopp.b2clogin.com/devsmittestopp.onmicrosoft.com/oauth2/v2.0/authorize?p=B2C_1A_phone_SUSI&client_id=<client_id>&nonce=defaultNonce&redirect_uri=https%3A%2F%2Fjwt.ms&scope=https%3A%2F%2Fdevsmittestopp.onmicrosoft.com%2Fbackend%2FDevice.Write&response_type=token&prompt=login)
to follow B2C login and get a token which can be used to access the API.

# Local development

This section if meant for developers that need to do local development of the backend.

## Getting the secrects

In order to do local development, you first need to unlock the secrets in the [`secrects`](secrets) folder. These files are encrypted and can be decrypted using [`git-crypt`](https://github.com/AGWA/git-crypt/blob/master/INSTALL.md). For this you need to get authorized by an administrator that can provide a key using [`ssh-vault`](https://ssh-vault.com). Once you get the key, then copy the key into a file on your machine (e.g `~/.key`), change directory into this repo and execute the command `cat ~/.key | ssh-vault view | git unlock -`. This will decrypt the encrypted files and you should now be able to read e.g [`secrets/dev/env-file`](secrets/dev/env-file).

## Source the secrets

When you have unlocked the secrets you need to export the variables in the [`env-file`](secrets/dev/env-file) as environment variables. On unix you can do the following

```
set -a && source secrets/dev/env-file && set +a
```

## Vulnerability scanning

[Trivy](https://github.com/aquasecurity/trivy) is used for vulnerability scanning of the images, as part of `make push/{image}`. One easy way to get trivy is by

```
curl -OL https://github.com/aquasecurity/trivy/releases/download/v0.6.0/trivy_0.6.0_Linux-64bit.tar.gz
tar zxf trivy_0.6.0_Linux-64bit.tar.gz trivy
sudo mv trivy /usr/local/bin/.
rm trivy_0.6.0_Linux-64bit.tar.gz
```

## Running the images

There are two ways to run the images in the [`images`](images) directory, either you can build the docker image and spin up a container, or you can create a (python) virtual environment and install the requirements there. The latter is more lightweight and you can do faster development, however the environment is not guaranteed to be identical to the environment running in the cloud.

As an example we will see how to run the [`corona`](images/corona) assuming your starting point in the in same directory as this README file.

### Using virtual environments

Change directory in the image directory

```
cd images/corona
```

Create a and activate virtual environment

```
python -m virtualenv venv
source venv/bin/activate
```

Install the dependencies

```
python -m pip install -r requirements.txt
```

Note the the `requirements.txt` have pinned all the versions of thr dependencies. The dependencies are listed in the `requirements.in` file and the `requirements.txt` is auto-generated using a tool called [`pip-compile`](https://pypi.org/project/pip-tools/)

If everything is set up correctly (and you have sourced the secrets) you should now be able to execute the command

```
python -m corona_backend
```

To check that everything works correctly go to `http://localhost:8080/health` and you should a message saying `ok`.

### Using docker

TBW

### Troubleshooting

1. If you get the following error message when trying to run the server

```
File ".../src/corona/corona/backend/images/corona/corona_backend/devices.py", line 39, in <module>
    r"hostname=([^;]+);", iothub_connection_str, flags=re.IGNORECASE
AttributeError: 'NoneType' object has no attribute 'group'
```

then the problem is that the variable `IOTHUB_CONNECTION_STRING` has not been parsed correctly. To fix this, open the [`env-file`](secrets/dev/env-file) and put quotation marks (") around the value of `IOTHUB_CONNECTION_STRING`. After sourcing this file again `set -a && source secrets/dev/env-file && set +a`, it should hopefully work.

# Azure Pipelines setup

(notes - to be updated)

We are using Azure Devops as a CI/CD platform. 

useClusterAdmin = true is requried for helm to be able to talk to AKS.
