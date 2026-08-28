#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
image_ref=localhost/spider-os:latest
if [ "$#" -gt 0 ]; then
  image_ref="$1"
fi

base_image="${SPIDER_BASE_IMAGE:-ghcr.io/ublue-os/aurora:stable}"

if ! command -v podman >/dev/null 2>&1; then
  printf '%s\n' "Podman is required to build the Spider OS image."
  exit 1
fi

sudo podman build \
  --pull=newer \
  --build-arg "BASE_IMAGE=$base_image" \
  --tag "$image_ref" \
  "$project_root"

sudo podman run --rm "$image_ref" bootc container lint
printf 'Built %s from %s\n' "$image_ref" "$base_image"
