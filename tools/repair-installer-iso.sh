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

for command in xorriso xz cpio grep; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command not found: $command" >&2
    exit 1
  }
done

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
mkdir -p "$workdir/grub" "$workdir/stamp"

# Record the boot equipment produced by bootc-image-builder. GRUB configuration
# is commonly embedded in the EFI El Torito image rather than exposed as a
# normal /EFI/BOOT/grub.cfg file in the ISO filesystem. Do not mistake that
# layout for a non-bootable ISO.
echo "Input ISO boot equipment:"
xorriso -indev "$input_iso" -report_el_torito plain 2>&1 | tee "$workdir/input-el-torito.txt"

grep -Eq 'BIOS[[:space:]]+y' "$workdir/input-el-torito.txt" || {
  echo "input ISO has no bootable BIOS El Torito image" >&2
  exit 1
}
grep -Eq 'UEFI[[:space:]]+y' "$workdir/input-el-torito.txt" || {
  echo "input ISO has no bootable UEFI El Torito image" >&2
  exit 1
}

# The legacy bootc Anaconda ISO path currently creates /.buildstamp but asks
# dracut to install ./buildstamp. Add the correctly named metadata file to the
# finished initramfs so Anaconda can see Spider OS product metadata in early
# userspace. This is the boot-critical repair; menu branding is not allowed to
# break an otherwise valid installer.
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

cpio_archive="$workdir/initrd.cpio"
xz -dc "$initrd" > "$cpio_archive"
(
  cd "$workdir/stamp"
  printf '.buildstamp\0' | cpio --null -o -H newc -A -F "$cpio_archive" >/dev/null 2>&1
)

repaired_initrd="$workdir/initrd-repaired.img"
xz --check=crc32 -9e -c "$cpio_archive" > "$repaired_initrd"
xz -dc "$repaired_initrd" | cpio -it --quiet | grep -Fx '.buildstamp' >/dev/null

# If the builder happens to expose GRUB configs in the ISO filesystem, rebrand
# their visible menu title. Many current bootc-image-builder ISOs keep GRUB's
# config inside the EFI boot image instead, so absence of an outer grub.cfg is
# expected and MUST NOT fail the installer build.
mapfile -t grub_paths < <(
  xorriso -indev "$input_iso" -find / -type f -name grub.cfg -print 2>/dev/null
)

xorriso_args=(-indev "$input_iso" -outdev "$output_iso" -overwrite on)
patched_menu=0
index=0
if [ "${#grub_paths[@]}" -eq 0 ]; then
  echo "No outer ISO grub.cfg found; preserving embedded GRUB/EFI boot configuration unchanged."
else
  command -v sed >/dev/null 2>&1 || {
    echo "required command not found: sed" >&2
    exit 1
  }
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
fi

# Replace only the initrd and product metadata while replaying the exact hybrid
# BIOS/UEFI boot equipment from the source ISO. The boot catalog, EFI image,
# bootloader binaries and embedded GRUB configuration remain builder-owned.
xorriso_args+=(
  -map "$repaired_initrd" /images/pxeboot/initrd.img
  -map "$buildstamp" /.buildstamp
  -boot_image any replay
  -compliance no_emul_toc
  -padding included
)

rm -f "$output_iso"
xorriso "${xorriso_args[@]}" >/dev/null

# Bootability checks are deliberately about boot equipment, not cosmetic menu
# text. Both BIOS and UEFI entries must survive the rewrite and the repaired
# initramfs must contain Spider OS metadata.
xorriso -indev "$output_iso" -report_el_torito plain > "$workdir/output-el-torito.txt" 2>&1
grep -Eq 'BIOS[[:space:]]+y' "$workdir/output-el-torito.txt"
grep -Eq 'UEFI[[:space:]]+y' "$workdir/output-el-torito.txt"

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

if [ "$patched_menu" -eq 1 ]; then
  echo "Spider OS installer ISO repaired; outer GRUB menu branding updated."
else
  echo "Spider OS installer ISO repaired; embedded bootloader configuration preserved."
fi
echo "Verified bootable BIOS+UEFI ISO: $output_iso"
