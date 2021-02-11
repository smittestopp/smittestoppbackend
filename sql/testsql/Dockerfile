FROM mcr.microsoft.com/mssql/server:2019-CU4-ubuntu-16.04 as builder
USER root
RUN apt-get update \
 && apt-get -y dist-upgrade \
 && apt-get -y install curl gnupg
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
 && curl https://packages.microsoft.com/config/ubuntu/16.04/prod.list > /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update \
 && ACCEPT_EULA=Y apt-get -y install \
    msodbcsql17 \
    unixodbc \
 && apt-get update && apt-get install -yq \
    python3 \
    python3-dev \
    python3-pip \
    unixodbc-dev \
    build-essential

RUN python3 -mpip install --no-cache --upgrade pip
COPY requirements.txt /tmp/requirements.txt
RUN python3 -mpip install --no-cache -r /tmp/requirements.txt

COPY . /srv
WORKDIR /srv

