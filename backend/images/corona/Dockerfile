FROM ubuntu:19.10 as builder
RUN apt-get update && apt-get install -yq \
    python3 \
    python3-dev \
    python3-pip \
    unixodbc-dev \
    build-essential

RUN python3 -mpip install --upgrade pip
COPY requirements.txt /tmp/
RUN pip wheel -w /wheelhouse -r /tmp/requirements.txt

FROM ubuntu:19.10
RUN apt-get update \
 && apt-get -y dist-upgrade \
 && apt-get -y install curl gnupg
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
 && curl https://packages.microsoft.com/config/ubuntu/19.10/prod.list > /etc/apt/sources.list.d/mssql-release.list

RUN apt-get update \
 && ACCEPT_EULA=Y apt-get -y install \
    msodbcsql17 \
    unixodbc \
 && apt-get update && apt-get install -yq \
    --no-install-recommends \
    python3 \
    python3-pip \
    python3-pycurl

RUN python3 -mpip install --no-cache --upgrade pip
COPY --from=builder /wheelhouse /wheelhouse
RUN python3 -mpip install --no-cache /wheelhouse/*.whl
COPY corona_backend /srv/corona_backend
ENV PORT=8080
EXPOSE 8080
ENV PYTHONPATH=/srv:$PYTHONPATH
CMD python3 -m corona_backend.onboarding
# remove bash to avoid warnings about CVE-2019-18276
RUN apt-get -y --allow-remove-essential remove bash --purge

# Folder needed by Azure Monitor Log Handler (opencensus).  
RUN mkdir -p .opencensus/.azure \
 && chmod 750 .opencensus/.azure -R \
 && chown nobody:nogroup .opencensus/.azure -R

ENV HOME=/tmp
# uid must be in /etc/passwd for odbc to initialize!
# this is bizarre
USER nobody
