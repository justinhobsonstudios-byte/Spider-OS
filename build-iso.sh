#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$script_dir/Containerfile" ]; then
  project_root="$script_dir"
else
  project_root="$(cd "$script_dir/.." && pwd)"
fi

image_ref="${1:-localhost/spider-os:latest}"
output_dir="$project_root/output"

if ! command -v podman >/dev/null 2>&1; then
  printf '%s\n' "Podman is required to build the Spider OS installer."
  exit 1
fi

build_script=""
if [ -f "$project_root/build-image.sh" ]; then
  build_script="$project_root/build-image.sh"
elif [ -f "$project_root/distro/build-image.sh" ]; then
  build_script="$project_root/distro/build-image.sh"
else
  printf '%s\n' "Could not find the Spider OS image build script." >&2
  exit 1
fi

bash "$build_script" "$image_ref"
mkdir -p "$output_dir"

sudo podman run \
  --rm \
  --privileged \
  --pull=newer \
  --security-opt label=type:unconfined_t \
  --volume "$output_dir:/output" \
  --volume /var/lib/containers/storage:/var/lib/containers/storage \
  quay.io/centos-bootc/bootc-image-builder:latest \
  --type anaconda-iso \
  --rootfs btrfs \
  --chown "$(id -u):$(id -g)" \
  "$image_ref"

printf 'Spider OS installer output: %s\n' "$output_dir"
