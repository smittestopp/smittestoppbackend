RELEASE ?= dev
SHELL := /bin/bash

ifeq ($(RELEASE),prod)
	AZ_SUB = <insert prod subscription id>
	AZ_RG = rg-smittestopp-prod
	AZ_AKS_NAME = aks-smittestopp-prod-north
else
	AZ_SUB = <insert dev subscription id>
	AZ_RG = rg-smittestopp-dev
	AZ_AKS_NAME = aks-smittestopp-dev-1
endif

# docker images for services

IMAGE_PREFIX ?= smittestopp/
ACR_NAME = acrsmittestopp$(RELEASE)

job_prefixes := "build trivy images push"
images := corona analysis delete
image_targets := $(foreach job,$(job_prefixes),$(foreach image,$(images),$(job)/$(notdir $(image))))


.PHONY: terraform FORCE

FORCE:

images/%/requirements.txt: images/%/requirements.in
	cd images/$* && CUSTOM_COMPILE_COMMAND="make $@" pip-compile

tag/%: FORCE
	$(eval EXTRA := $(shell if [[ $* == delete ]]; then echo "images/corona"; fi))
	$(eval DIRTY := $(shell git diff --exit-code --name-only HEAD -- images/$* $(EXTRA) 1>&2 || echo '.dirty'))
	$(eval COMMIT_STAMP := $(shell git log -1 --format='%aI:%h' -- images/$*  $(EXTRA) | cut -f 1,2,5 -d ':' | sed 's/:/./g'))
	$(eval IMAGE := $(ACR_NAME).azurecr.io/$(IMAGE_PREFIX)$*)
	$(eval IMAGE_TAG := $(IMAGE):$(COMMIT_STAMP)$(DIRTY))
	@echo $(IMAGE_TAG)


tags: $(foreach image,$(images),tag/$(image))


build/%: images/%/requirements.txt tag/% FORCE
	$(eval CORONA_IMAGE := $(shell if [[ $* != corona ]]; then make tag/corona RELEASE=$(RELEASE); fi))
	$(eval IMAGE_EXISTS := $(shell docker images -q $(IMAGE_TAG) 2>/dev/null))
	$(shell if [[ -z "$(IMAGE_EXISTS)" || ! -z "$(DIRTY)" ]]; then \
		echo "docker build \
		--build-arg CORONA_IMAGE=$(CORONA_IMAGE) \
		-t $(IMAGE) \
		-t $(IMAGE_TAG) \
		images/$*"; \
	else echo "@echo already have $(IMAGE_TAG)";\
	fi)


trivy/%: build/% FORCE
	trivy --severity HIGH,CRITICAL --exit-code=1 $(IMAGE_TAG)

# verify that the given image is not dirty (prior to upload)
notdirty/%: tag/% FORCE
	@test -z "$(DIRTY)" -o "$(RELEASE)" == "dev"

acrlogin:
	az acr login --name $(ACR_NAME)

push/%: acrlogin notdirty/% trivy/% FORCE
	docker push $(IMAGE):$(COMMIT_STAMP)$(DIRTY)
	docker push $(IMAGE):latest

push: $(foreach image,$(images),push/$(image))

images/%: push/% FORCE

images: $(foreach image,$(images),images/$(image))

pushed-tags/%:
	az acr repository show-tags \
		--subscription $(AZ_SUB) \
		--name $(ACR_NAME) \
		--repository $(IMAGE_PREFIX)$*

pull-analysis:
	# inlined in this repo, so not necessary anymore
	cd ../; git subtree pull --prefix backend/images/analysis/corona-analysis git@github.com:<org>/<repo> stable --squash

update-dev-analysis: pull-analysis push/analysis kube-ctx
	# restart analysis pods
	kubectl get pod -ndev | grep analysis | cut -f1 -d ' ' | xargs kubectl delete pod -ndev

# general dev utilities

dev-env:
	@echo $(shell cat secrets/dev/env-file | sed 's@#.*@@g' | awk NF | awk -F= '{st=index($$0,"="); print "export " $$1 "=\"" substr($$0,st+1) "\"\\;"}')
	@echo '# use `eval $$(make dev-env)` to set environment variables for dev testing'
	@echo '# requires git-crypt dev key'

# terraform deployment

terraform_module_dir = terraform/modules/smittestop
terraform_release_dir = terraform/$(RELEASE)

terraform_inputs = \
	$(terraform_module_dir)/variables.tf \
	$(terraform_module_dir)/resource.tf \
	$(terraform_module_dir)/outputs.tf \
	$(terraform_release_dir)/main.tf \
	$(terraform_release_dir)/variables.tf \
	$(terraform_release_dir)/$(RELEASE).tfvars \
	$(terraform_release_dir)/secrets/$(RELEASE).tfvars

$(terraform_release_dir)/.terraform: $(terraform_release_dir)/main.tf
	az account set -s $(AZ_SUB)
	cd $(terraform_release_dir); terraform init
	touch $(terraform_release_dir)/.terraform

terraform: $(terraform_release_dir)/.terraform
	az account set -s $(AZ_SUB)
	cd $(terraform_release_dir); terraform apply \
		-parallelism=32 \
		-var-file=$(RELEASE).tfvars \
		-var-file=secrets/$(RELEASE).tfvars \
		$(TF_ARGS)

terraform-force:
	touch terraform/resource.tf
	make terraform RELEASE=$(RELEASE)


# secret-related

%.pfx: %.crt %.key
	openssl pkcs12 -passout pass: -export -out $*.pfx -inkey $*.key -in $*.crt

certificates: $(foreach name,ca apim server,secrets/$(RELEASE)/ssl/$(name)/$(name).pfx)

# kubernetes

aks-group-ids:
	az ad group list | jq -r '.[] | .displayName + ": " + .objectId' | grep AKS | sort

# make sure we run all kubernetes commands against the current cluster
ADMIN_KUBECONFIG := $(PWD)/secrets/kubeconfig.$(RELEASE).json

kube-creds:
	az account set -s $(AZ_SUB)
	az aks get-credentials --resource-group $(AZ_RG) --name $(AZ_AKS_NAME)
	kubectl config set-context $(AZ_AKS_NAME) --namespace=$(RELEASE)
	kubectl get pod

helm-admin-init:
	KUBECONFIG=$(ADMIN_KUBECONFIG) helm install --namespace corona-admin corona-roles helm/admin/chart -f helm/admin/config/$(RELEASE).yaml

helm-admin:
	KUBECONFIG=$(ADMIN_KUBECONFIG) helm upgrade --namespace corona-admin corona-roles helm/admin/chart -f helm/admin/config/$(RELEASE).yaml

$(KUBECONFIG):
	az account set -s $(AZ_SUB)
	cd terraform/$(RELEASE); terraform output kube_config > $(KUBECONFIG)
	KUBECONFIG=$(ADMIN_KUBECONFIG) kubectl config set-context --current --namespace=$(RELEASE)

kube-config: $(KUBECONFIG)

kube-env:
	@echo "export KUBECONFIG=$(KUBECONFIG)\n"
	@echo "# run these lines to connect to the kubernetes cluster for $(RELEASE)\n"
	@echo '# or use with eval `make kube-env`'

kube-env-unset:
	@echo "# run these lines to disconnect from the kubernetes cluster $(RELEASE)\n"
	@echo "unset KUBECONFIG"

kube-check: kube-ctx
	kubectl get pod

kube-ctx: FORCE
	kubectl config use-context $(AZ_AKS_NAME)
	kubectl config set-context $(AZ_AKS_NAME) --namespace=$(RELEASE)

helm/chart/charts: helm/chart/requirements.yaml
	rm -rf helm/chart/charts
	helm dep up ./helm/chart
	touch helm/chart/charts

helm-dependencies: helm/chart/charts

helm/admin/chart/charts: helm/admin/chart/requirements.yaml
	rm -rf helm/admin/chart/charts
	helm dep up ./helm/admin/chart
	touch helm/admin/chart/charts

helm-admin-dependencies: helm/admin/chart/charts

helm-ls:
	helm ls

HELM_ARGS = corona-$(RELEASE) \
	./helm/chart \
	-f ./helm/config/common.yaml \
	-f ./helm/config/$(RELEASE).yaml \
	-f ./helm/secrets/$(RELEASE).yaml

helm-install: kube-ctx helm-dependencies
	helm version --short | grep "v3"
	kubectl create namespace $(RELEASE)
	helm install --namespace $(RELEASE) $(HELM_ARGS)

helm-diff: kube-ctx
	helm diff upgrade $(HELM_ARGS)

helm-upgrade: helm-dependencies helm-diff
	helm version --short | grep "v3"
	helm upgrade $(HELM_ARGS)


node-rg:
	$(eval NODE_RG := \
		$(shell az aks show \
			--subscription $(AZ_SUB) \
			--resource-group $(AZ_RG) \
			--name $(AZ_AKS_NAME) \
			--query nodeResourceGroup \
			-o tsv \
		) \
	)


get-aks-ips: node-rg
	@echo "the egress ip is the one with tag type: aks-slb-managed-outbound-ip"
	az network public-ip list \
		--subscription $(AZ_SUB) \
		--resource-group $(NODE_RG) \
	| jq '.[] | "\(.name) \(.ipAddress) \(.tags)"'

static-ip: node-rg
# 	az network public-ip list \
# 		--subscription $(AZ_SUB) \
# 		--resource-group $(NODE_RG) | jq '.[] | "\(.name) \(.ipAddress)"'
	# running create multiple times with the same name is idempotent
	az network public-ip create \
		--subscription $(AZ_SUB) \
		--resource-group $(NODE_RG) \
		--name egress-aks-smittestopp-$(RELEASE) \
		--allocation-method static | jq .publicIp.ipAddress


LETSENCRYPT_DIR = secrets/letsencrypt
LETSENCRYPT_ARGS = --server https://acme-v02.api.letsencrypt.org/directory --logs-dir=$(LETSENCRYPT_DIR)/logs --config-dir=$(LETSENCRYPT_DIR)/config --work-dir=$(LETSENCRYPT_DIR)/work
LIVE_DIR = $(LETSENCRYPT_DIR)/config/live/$(RELEASE).corona.nntb.no

$(LETSENCRYPT_DIR)/$(RELEASE).pfx: $(LIVE_DIR)/privkey.pem $(LIVE_DIR)/fullchain.pem
	openssl pkcs12 -export -out $(LETSENCRYPT_DIR)/$(RELEASE).pfx -inkey $(LETSENCRYPT_DIR)/config/live/$(RELEASE).corona.nntb.no/privkey.pem -in $(LETSENCRYPT_DIR)/config/live/$(RELEASE).corona.nntb.no/fullchain.pem

$(LETSENCRYPT_DIR)/$(RELEASE).pem: $(LIVE_DIR)/privkey.pem $(LIVE_DIR)/fullchain.pem
	cat $(LIVE_DIR)/privkey.pem > $@
	cat $(LIVE_DIR)/fullchain.pem >> $@

letsencrypt: FORCE
	# certbot certonly --manual --preferred-challenges dns -d "$(RELEASE).corona.nntb.no,*.$(RELEASE).corona.nntb.no" $(LETSENCRYPT_ARGS)
	openssl pkcs12 -export -out $(LETSENCRYPT_DIR)/$(RELEASE).pfx -inkey $(LETSENCRYPT_DIR)/config/live/$(RELEASE).corona.nntb.no/privkey.pem -in $(LETSENCRYPT_DIR)/config/live/$(RELEASE).corona.nntb.no/fullchain.pem

ssl-request: letsencrypt $(LETSENCRYPT_DIR)/$(RELEASE).pfx $(LETSENCRYPT_DIR)/$(RELEASE).pem
