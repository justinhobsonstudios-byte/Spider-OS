#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
image_ref=localhost/spider-os:latest
if [ "$#" -gt 0 ]; then
  image_ref="$1"
fi
output_dir="$project_root/output"

if ! command -v podman >/dev/null 2>&1; then
  printf '%s\n' "Podman is required to build the Spider OS installer."
  exit 1
fi

"$project_root/distro/build-image.sh" "$image_ref"
mkdir -p "$output_dir"

sudo podman run \
  --rm \
  --privileged \
  --pull=newer \
  --security-opt label=type:unconfined_t \
  --volume "$output_dir:/output" \
  --volume /var/lib/containers/storage:/var/lib/containers/storage \
  quay.io/centos-bootc/bootc-image-builder:latest \
  --type iso \
  --rootfs btrfs \
  --chown "$(id -u):$(id -g)" \
  "$image_ref"

printf 'Spider OS installer output: %s\n' "$output_dir"

