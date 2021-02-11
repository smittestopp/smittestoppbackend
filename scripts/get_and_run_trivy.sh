#!/usr/bin/env bash

binary="trivy"
declare -i retrycount=${3:-0}
curlok="false"
trap 'echo "Error in trivy-run";  if [[ ${retrycount} -lt 3 && ${curlok} = "false" ]] ; then echo "Retry"; $0 $1 $2 $((retrycount+1)); else exit 1; fi' ERR

set -x

# get trivy (we need to cache this maybe)
if [[ ! -x ${binary} ]] ; then 
	curl --retry-max-time 5 --retry 5 -OL https://github.com/aquasecurity/trivy/releases/download/v0.6.0/trivy_0.6.0_Linux-64bit.tar.gz
	tar zxf trivy_0.6.0_Linux-64bit.tar.gz ${binary}
	rm trivy_0.6.0_Linux-64bit.tar.gz
	chmod 755 ${binary}
	curlok="true"
fi

img="$1/$2"
# scripts run with the folder the script is located in as $CWD
./${binary} --ignorefile=../backend/.trivyignore --severity HIGH,CRITICAL --exit-code=1 ${img}
