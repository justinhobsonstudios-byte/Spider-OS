#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$script_dir/Containerfile" ]; then
  project_root="$script_dir"
else
  project_root="$(cd "$script_dir/.." && pwd)"
fi

image_ref="${1:-localhost/spider-os:latest}"
base_image="${SPIDER_BASE_IMAGE:-ghcr.io/ublue-os/aurora:stable}"

if ! command -v podman >/dev/null 2>&1; then
  printf '%s\n' "Podman is required to build the Spider OS image."
  exit 1
fi

if [ ! -f "$project_root/Containerfile" ]; then
  printf 'Containerfile not found under %s\n' "$project_root" >&2
  exit 1
fi

for required in build_files system_files src/spider_os; do
  if [ ! -e "$project_root/$required" ]; then
    printf 'Spider OS source tree is incomplete: missing %s\n' "$required" >&2
    printf '%s\n' "Restore the image-template folders before building locally." >&2
    exit 1
  fi
done

sudo podman build \
  --pull=newer \
  --build-arg "BASE_IMAGE=$base_image" \
  --file "$project_root/Containerfile" \
  --tag "$image_ref" \
  "$project_root"

sudo podman run --rm "$image_ref" bootc container lint
printf 'Built %s from %s\n' "$image_ref" "$base_image"
