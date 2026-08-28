#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <input.iso> <output.iso>" >&2
  exit 2
fi

input_iso="$(realpath "$1")"
output_iso="$2"

if [ ! -f "$input_iso" ]; then
  echo "input ISO not found: $input_iso" >&2
  exit 1
fi

for command in xorriso xz cpio sed; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command not found: $command" >&2
    exit 1
  }
done

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
mkdir -p "$workdir/grub" "$workdir/stamp"

# Refuse to rewrite media that did not arrive with a hybrid boot layout. This
# also proves the builder supplied boot equipment before we touch the ISO.
xorriso -indev "$input_iso" -report_el_torito plain > "$workdir/source-el-torito.txt" 2>&1
cat "$workdir/source-el-torito.txt"
grep -Eiq 'BIOS' "$workdir/source-el-torito.txt"
grep -Eiq 'UEFI' "$workdir/source-el-torito.txt"

# The legacy bootc Anaconda ISO path currently creates /.buildstamp but asks
# dracut to install ./buildstamp. Add the correctly named file to the finished
# initramfs so Anaconda has product metadata from its first userspace process.
buildstamp="$workdir/stamp/.buildstamp"
cat > "$buildstamp" <<EOF
[Main]
Product = Spider OS
Version = 0.7.0
IsFinal = True
UUID = $(date -u +%Y%m%d%H%M).x86_64

[Compose]
osbuild = Spider OS
EOF

initrd="$workdir/initrd.img"
xorriso -osirrox on -indev "$input_iso" \
  -extract /images/pxeboot/initrd.img "$initrd" >/dev/null 2>&1
test -s "$initrd"

cpio_archive="$workdir/initrd.cpio"
xz -dc "$initrd" > "$cpio_archive"
test -s "$cpio_archive"
(
  cd "$workdir/stamp"
  printf '.buildstamp\0' | cpio --null -o -H newc -A -F "$cpio_archive" >/dev/null 2>&1
)

repaired_initrd="$workdir/initrd-repaired.img"
xz --check=crc32 -9e -c "$cpio_archive" > "$repaired_initrd"
test -s "$repaired_initrd"
xz -dc "$repaired_initrd" | cpio -it --quiet | grep -Fx '.buildstamp' >/dev/null

# bootc-image-builder can place GRUB configuration inside its EFI boot image
# instead of exposing grub.cfg as a normal ISO filesystem file. A missing
# standalone grub.cfg is therefore NOT a boot failure. Patch menu branding only
# when a text configuration is directly available, and never sacrifice a valid
# hybrid ISO merely because the menu title cannot be edited in place.
mapfile -t grub_paths < <(
  xorriso -indev "$input_iso" -find / -type f -name grub.cfg -print 2>/dev/null || true
)

xorriso_args=(-indev "$input_iso" -outdev "$output_iso" -overwrite on)
patched_menu=0
index=0

if [ "${#grub_paths[@]}" -eq 0 ]; then
  echo "No standalone grub.cfg found in ISO filesystem; preserving embedded GRUB boot image unchanged."
  echo "GRUB/EFI-related files visible in ISO filesystem:"
  xorriso -indev "$input_iso" -find / -type f -exec report_lba -- 2>/dev/null \
    | grep -Ei 'grub|efi|boot|isolinux' \
    | head -n 100 || true
else
  for iso_path in "${grub_paths[@]}"; do
    index=$((index + 1))
    local_cfg="$workdir/grub/grub-${index}.cfg"
    xorriso -osirrox on -indev "$input_iso" -extract "$iso_path" "$local_cfg" >/dev/null 2>&1

    if grep -Eq 'Aurora[[:space:]]+[0-9]+' "$local_cfg"; then
      sed -E -i 's/Aurora[[:space:]]+[0-9]+/Spider OS/g' "$local_cfg"
      patched_menu=1
    fi

    xorriso_args+=(-map "$local_cfg" "$iso_path")
  done

  if [ "$patched_menu" -ne 1 ]; then
    echo "No Aurora title found in standalone GRUB config; leaving its menu text unchanged." >&2
  fi
fi

# Place Spider OS metadata both in the installer initramfs and at ISO root.
# Replay the original hybrid BIOS/UEFI boot equipment byte-for-byte as far as
# xorriso permits so we retain the builder's known-good boot arrangement.
xorriso_args+=(
  -map "$repaired_initrd" /images/pxeboot/initrd.img
  -map "$buildstamp" /.buildstamp
  -boot_image any replay
  -compliance no_emul_toc
  -padding included
)

rm -f "$output_iso"
xorriso "${xorriso_args[@]}" >/dev/null

# Bootability is the release gate. Verify that the repaired media still has
# both BIOS and UEFI El Torito entries and that .buildstamp really survived in
# the initramfs. Menu branding is verified only when we actually patched it.
xorriso -indev "$output_iso" -report_el_torito plain > "$workdir/el-torito.txt" 2>&1
cat "$workdir/el-torito.txt"
grep -Eiq 'BIOS' "$workdir/el-torito.txt"
grep -Eiq 'UEFI' "$workdir/el-torito.txt"

if [ "$patched_menu" -eq 1 ]; then
  verified_menu=0
  mapfile -t repaired_grub_paths < <(
    xorriso -indev "$output_iso" -find / -type f -name grub.cfg -print 2>/dev/null || true
  )
  for iso_path in "${repaired_grub_paths[@]}"; do
    index=$((index + 1))
    local_cfg="$workdir/grub/verify-${index}.cfg"
    xorriso -osirrox on -indev "$output_iso" -extract "$iso_path" "$local_cfg" >/dev/null 2>&1
    if grep -Fq 'Install Spider OS' "$local_cfg"; then
      verified_menu=1
    fi
    if grep -Eq 'Install Aurora[[:space:]]+[0-9]+' "$local_cfg"; then
      echo "Aurora installer title remains in $iso_path" >&2
      exit 1
    fi
  done
  test "$verified_menu" -eq 1
fi

verify_initrd="$workdir/verify-initrd.img"
xorriso -osirrox on -indev "$output_iso" \
  -extract /images/pxeboot/initrd.img "$verify_initrd" >/dev/null 2>&1
mkdir -p "$workdir/verify-stamp"
(
  cd "$workdir/verify-stamp"
  xz -dc "$verify_initrd" | cpio -id --quiet '.buildstamp'
)
grep -Fq 'Product = Spider OS' "$workdir/verify-stamp/.buildstamp"
grep -Fq 'Version = 0.7.0' "$workdir/verify-stamp/.buildstamp"

root_buildstamp="$workdir/root-buildstamp"
xorriso -osirrox on -indev "$output_iso" -extract /.buildstamp "$root_buildstamp" >/dev/null 2>&1
grep -Fq 'Product = Spider OS' "$root_buildstamp"

echo "Spider OS installer ISO boot metadata repaired and verified: $output_iso"
if [ "$patched_menu" -eq 0 ]; then
  echo "Installer menu branding was intentionally left untouched because GRUB configuration is embedded by the ISO builder."
fi
