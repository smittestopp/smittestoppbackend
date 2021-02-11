ARG CORONA_IMAGE
FROM ubuntu:19.10 as builder
RUN apt-get update && apt-get install -yq \
    python3 \
    python3-dev \
    python3-pip \
    build-essential

RUN python3 -mpip install --upgrade pip
COPY requirements.txt /tmp/
RUN python3 -mpip wheel -w /wheelhouse -r /tmp/requirements.txt

ARG CORONA_IMAGE
FROM ${CORONA_IMAGE}

USER root

COPY --from=builder /wheelhouse /wheelhouse
RUN python3 -mpip install --no-cache /wheelhouse/*.whl

COPY corona_delete /srv/corona_delete
CMD python3 -m corona_delete.delete

# uid must be in /etc/passwd for odbc to initialize!
# this is bizarre
USER nobody
