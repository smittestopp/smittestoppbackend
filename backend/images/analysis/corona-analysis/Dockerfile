FROM python:3.8
RUN apt-get update && \
    apt-get -y install python3-rtree unixodbc unixodbc-dev
COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
COPY corona /srv/corona
COPY docker/corona.conf ~/.config
ENV PORT=8080
EXPOSE 8080
ENV PYTHONPATH=/srv:$PYTHONPATH
CMD python -m corona
USER 65535
