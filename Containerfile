# Spider OS bootc image
# Structural reference: Universal Blue image-template

ARG BASE_IMAGE=ghcr.io/ublue-os/aurora:stable

FROM scratch AS ctx

COPY build_files /
COPY system_files /system_files
COPY src/spider_os /spider_os

FROM ${BASE_IMAGE}

LABEL containers.bootc="1"
LABEL org.opencontainers.image.title="Spider OS"
LABEL org.opencontainers.image.description="A local-first AI operating system for the whole life"
LABEL org.opencontainers.image.licenses="MIT"

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    /bin/bash /ctx/build.sh

RUN bootc container lint
