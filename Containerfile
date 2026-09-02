ARG BASE_IMAGE=ghcr.io/ublue-os/aurora:stable

FROM scratch AS ctx
COPY build_files /build_files
COPY system_files /system_files

FROM ${BASE_IMAGE}

LABEL containers.bootc="1"
LABEL org.opencontainers.image.title="Spider OS Minimal Installer Rebuild"
LABEL org.opencontainers.image.description="Aurora KDE bootc image with the smallest verified Spider OS overlay"

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    /bin/bash /ctx/build_files/build.sh

RUN bootc container lint
