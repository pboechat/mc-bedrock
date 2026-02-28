# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies via shared script
ARG BLUEMAP_VERSION=5.16
COPY install-deps.sh /tmp/install-deps.sh
RUN chmod +x /tmp/install-deps.sh && \
    /tmp/install-deps.sh "$BLUEMAP_VERSION" false /opt/bluemap && \
    rm /tmp/install-deps.sh

COPY mapper.py /usr/local/bin/mapper.py
RUN chmod +x /usr/local/bin/mapper.py

EXPOSE 80
ENTRYPOINT ["python", "/usr/local/bin/mapper.py"]
