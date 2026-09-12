#!/usr/bin/env bash
set -euo pipefail

project_root="${1:-.}"
pack_root="$project_root/system_files/usr/share/spider-os/creative-packs"
installer="$project_root/system_files/usr/bin/spider-creative-pack"
launcher="$project_root/system_files/usr/share/applications/spider-creative-studio.desktop"
expected_packs=(audio visual video publishing)
all_apps="$(mktemp -t spider-creative-apps.XXXXXXXX)"
trap 'rm -f -- "$all_apps"' EXIT

test -d "$pack_root"
test -f "$installer"
test -f "$launcher"
bash -n "$installer"

for pack in "${expected_packs[@]}"; do
  list="$pack_root/$pack.list"
  test -s "$list"
  sed \
    -e 's/[[:space:]]*#.*$//' \
    -e '/^[[:space:]]*$/d' \
    "$list" >> "$all_apps"
done

if ! awk '/^[A-Za-z0-9]+([._-][A-Za-z0-9]+)+$/ { next } { exit 1 }' "$all_apps"; then
  printf '%s\n' "A creative pack contains an invalid Flatpak application ID." >&2
  exit 1
fi

app_count="$(wc -l < "$all_apps")"
unique_count="$(sort -u "$all_apps" | wc -l)"
if [ "$app_count" -ne 17 ] || [ "$unique_count" -ne 17 ]; then
  printf 'Expected 17 unique creative applications; found %s entries and %s unique IDs.\n' \
    "$app_count" "$unique_count" >&2
  exit 1
fi

grep -Fxq 'Exec=spider-creative-pack gui' "$launcher"
grep -Fq 'pipewire-jack-audio-connection-kit' "$project_root/build_files/build.sh"
grep -Fq 'qpwgraph' "$project_root/build_files/build.sh"
grep -Fq 'rtkit' "$project_root/build_files/build.sh"

printf 'Validated four Spider Creative Studio packs with %s unique applications.\n' "$unique_count"
