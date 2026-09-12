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
source_root="$project_root"
temporary_source=""

cleanup() {
  if [ -n "$temporary_source" ] && [ -d "$temporary_source" ]; then
    rm -rf -- "$temporary_source"
  fi
}
trap cleanup EXIT

has_image_source() {
  [ -d "$1/build_files" ] && \
    [ -d "$1/system_files" ] && \
    [ -d "$1/src/spider_os" ]
}

if ! command -v podman >/dev/null 2>&1; then
  printf '%s\n' "Podman is required to build the Spider OS image."
  exit 1
fi

if [ ! -f "$project_root/Containerfile" ]; then
  printf 'Containerfile not found under %s\n' "$project_root" >&2
  exit 1
fi

if ! has_image_source "$source_root"; then
  source_archive="$project_root/Spider_OS_v0.7_GitHub_ISO_Ready.zip"
  if [ ! -f "$source_archive" ]; then
    printf '%s\n' "Spider OS image source folders and source archive are missing." >&2
    exit 1
  fi
  if ! command -v unzip >/dev/null 2>&1; then
    printf '%s\n' "unzip is required while the image source is stored in the source archive." >&2
    exit 1
  fi

  temporary_source="$(mktemp -d -t spider-os-source.XXXXXXXX)"
  unzip -q "$source_archive" -d "$temporary_source"
  source_root=""
  while IFS= read -r candidate_containerfile; do
    candidate_root="$(dirname "$candidate_containerfile")"
    if has_image_source "$candidate_root"; then
      source_root="$candidate_root"
      break
    fi
  done < <(find "$temporary_source" -type f -name Containerfile -print)

  if [ -z "$source_root" ]; then
    printf '%s\n' "The Spider OS source archive does not contain a complete image tree." >&2
    exit 1
  fi
fi

# The root build script and image overlay are canonical. Apply both whether
# the legacy source archive or a future normal source tree supplies the base.
install -m 0755 "$project_root/build.sh" "$source_root/build_files/build.sh"
if [ -d "$project_root/image_overlay" ]; then
  cp -a "$project_root/image_overlay/." "$source_root/"
fi

if [ -x "$project_root/tools/validate-creative-packs.sh" ]; then
  "$project_root/tools/validate-creative-packs.sh" "$source_root"
fi

sudo podman build \
  --pull=newer \
  --build-arg "BASE_IMAGE=$base_image" \
  --file "$project_root/Containerfile" \
  --tag "$image_ref" \
  "$source_root"

sudo podman run --rm "$image_ref" bootc container lint
printf 'Built %s from %s\n' "$image_ref" "$base_image"
