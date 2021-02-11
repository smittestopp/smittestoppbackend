FROM ubuntu:19.10 as builder
RUN apt-get update \
 && apt-get install -yq \
    python3 python3-dev python3-pip build-essential \
    libspatialindex-dev unixodbc-dev python3-rtree \
    libproj-dev libgeos-dev

RUN python3 -mpip install --upgrade pip
RUN pip install numpy
COPY requirements.txt /tmp/
RUN pip wheel -w /wheelhouse -r /tmp/requirements.txt

# COPY corona-analysis /srv/corona-analysis
# RUN pip wheel -w /wheelhouse /srv/corona-analysis

FROM ubuntu:19.10

RUN apt-get update \
 && apt-get -y dist-upgrade \
 && apt-get -y install curl gnupg
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
 && curl https://packages.microsoft.com/config/ubuntu/19.10/prod.list > /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update \
 && ACCEPT_EULA=Y apt-get -y install msodbcsql17 \
 && apt-get install -yq \
    --no-install-recommends \
    python3 python3-pip unixodbc libspatialindex5 python3-rtree \
    libproj13 libgeos-c1v5

RUN python3 -mpip install --no-cache --upgrade pip
COPY --from=builder /wheelhouse /wheelhouse
RUN pip install --no-cache /wheelhouse/*.whl

# corona-analysis package cannot be installed
# it must be copied into place
COPY corona-analysis/corona /srv/corona


# load empty corona.conf since analysis doesn't start without it
# even though it's unused
ENV XDG_CONFIG_HOME=/tmp \
    HOME=/tmp
COPY corona.conf ${XDG_CONFIG_HOME}/corona.conf

COPY rediswq.py /srv/
COPY worker.py /srv/
WORKDIR /srv

CMD python3 /srv/worker.py

# remove bash to avoid warnings about CVE-2019-18276
RUN apt-get -y --allow-remove-essential remove bash --purge

# Add cache-directory for OSM
RUN mkdir /__cache__
RUN mkdir /srv/__cache__
RUN chmod 1777 /__cache__
RUN chmod 1777 /srv/__cache__

USER nobody
