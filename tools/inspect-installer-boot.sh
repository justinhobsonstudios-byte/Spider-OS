#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "usage: $0 <installer.iso> [diagnostics.txt]" >&2
  exit 2
fi

iso="$(realpath "$1")"
out="${2:-/dev/stdout}"

if [ ! -f "$iso" ]; then
  echo "installer ISO not found: $iso" >&2
  exit 1
fi

for command in xorriso strings find grep; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command not found: $command" >&2
    exit 1
  }
done

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
bootdir="$workdir/boot-images"
mkdir -p "$bootdir"

# xorriso can extract El Torito/EFI boot equipment even when those files are
# not represented in the visible ISO filesystem. This is exactly the layout
# bootc-image-builder currently produces for Spider OS.
xorriso -osirrox on -indev "$iso" -extract_boot_images "$bootdir" >/dev/null 2>&1

{
  echo "Spider OS installer boot diagnostics"
  echo "ISO: $(basename "$iso")"
  echo
  echo "== ISO volume =="
  xorriso -indev "$iso" -pvd_info 2>&1 | grep -E 'Volume id|Volume Id|System Id|Application Id' || true
  echo
  echo "== El Torito =="
  xorriso -indev "$iso" -report_el_torito plain 2>&1 || true
  echo
  echo "== Extracted boot equipment =="
  find "$bootdir" -maxdepth 1 -type f -printf '%f\t%s bytes\n' | sort
  echo
  echo "== Boot strings relevant to installer source =="
  found=0
  while IFS= read -r image; do
    matches="$(strings -a "$image" | grep -E 'inst\.stage2|inst\.repo|root=live:|rd\.live|CDLABEL=|LABEL=|SPIDER_OS|Spider OS|Aurora 44|Install Aurora' || true)"
    if [ -n "$matches" ]; then
      found=1
      echo "--- $(basename "$image") ---"
      printf '%s\n' "$matches" | sort -u
    fi
  done < <(find "$bootdir" -maxdepth 1 -type f -name '*.img' -print | sort)
  if [ "$found" -eq 0 ]; then
    echo "No relevant plain-text boot strings found in extracted boot images."
  fi
} > "$out"

# UEFI El Torito images are commonly FAT filesystems. If mtools is present,
# inspect their files as well; failure is diagnostic rather than fatal because
# firmware layouts vary between builder versions.
if command -v mcopy >/dev/null 2>&1; then
  while IFS= read -r uefi; do
    uefi_dir="$workdir/uefi-$(basename "$uefi" .img)"
    mkdir -p "$uefi_dir"
    {
      echo
      echo "== UEFI filesystem: $(basename "$uefi") =="
      mdir -i "$uefi" -/ :: 2>&1 || true
    } >> "$out"
    if mcopy -s -i "$uefi" '::*' "$uefi_dir" >/dev/null 2>&1; then
      {
        echo "-- copied UEFI files --"
        find "$uefi_dir" -type f -printf '%P\n' | sort
        echo "-- UEFI file strings --"
        while IFS= read -r file; do
          strings -a "$file" | grep -E 'inst\.stage2|inst\.repo|root=live:|rd\.live|CDLABEL=|LABEL=|SPIDER_OS|Spider OS|Aurora 44|Install Aurora' || true
        done < <(find "$uefi_dir" -type f -print)
      } >> "$out"
    fi
  done < <(find "$bootdir" -maxdepth 1 -type f \( -name '*uefi*.img' -o -name '*efi.img' \) -print | sort -u)
fi

cat "$out"
