#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <Spider_OS.iso>" >&2
  exit 2
fi

SOURCE_ISO="$(readlink -f "$1")"
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_DIR="${SPIDER_QUALIFY_WORK_DIR:-$REPO_ROOT/out/qualification}"
QUAL_ISO="$WORK_DIR/Spider_OS_1.0_qualification.iso"
DISK="$WORK_DIR/spider-installed.qcow2"
INSTALL_SERIAL="$WORK_DIR/install-serial.log"
BOOT_SERIAL="$WORK_DIR/installed-serial.log"
MONITOR="$WORK_DIR/qemu-monitor.sock"
PIDFILE="$WORK_DIR/qemu.pid"

mkdir -p "$WORK_DIR"
rm -f "$QUAL_ISO" "$DISK" "$INSTALL_SERIAL" "$BOOT_SERIAL" "$MONITOR" "$PIDFILE"

for cmd in qemu-system-x86_64 qemu-img; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Missing command: $cmd" >&2; exit 2; }
done

bash "$REPO_ROOT/distro/build/make-qualification-iso.sh" "$SOURCE_ISO" "$QUAL_ISO"
qemu-img create -f qcow2 "$DISK" 80G >/dev/null

accel=(-accel 'tcg,thread=multi' -cpu max)
if [[ -c /dev/kvm && -r /dev/kvm && -w /dev/kvm ]]; then
  accel=(-accel kvm -cpu host)
fi

wait_for_exit() {
  local seconds="$1"
  local elapsed=0
  while (( elapsed < seconds )); do
    if [[ ! -f "$PIDFILE" ]]; then
      sleep 2
      elapsed=$((elapsed + 2))
      continue
    fi
    local pid
    pid="$(cat "$PIDFILE")"
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 10
    elapsed=$((elapsed + 10))
  done
  return 1
}

# stop_vm is invoked indirectly by the EXIT trap below.
# shellcheck disable=SC2317
stop_vm() {
  if [[ -f "$PIDFILE" ]]; then
    local pid
    pid="$(cat "$PIDFILE")"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PIDFILE" "$MONITOR"
}

capture_screen() {
  local target="$1"
  if [[ -S "$MONITOR" ]] && command -v socat >/dev/null 2>&1; then
    printf 'screendump %s\n' "$target" | socat - "UNIX-CONNECT:$MONITOR" >/dev/null 2>&1 || true
  fi
}

trap stop_vm EXIT

echo "[qualification] installing Spider OS to a clean virtual disk"
qemu-system-x86_64 \
  -machine q35 \
  "${accel[@]}" \
  -m 6144 \
  -smp 4 \
  -boot order=d \
  -cdrom "$QUAL_ISO" \
  -drive "file=$DISK,format=qcow2,if=virtio,cache=unsafe" \
  -device virtio-vga \
  -display none \
  -serial "file:$INSTALL_SERIAL" \
  -monitor "unix:$MONITOR,server=on,wait=off" \
  -pidfile "$PIDFILE" \
  -daemonize

# The qualification autoinstall powers the VM off when installation is complete.
if ! wait_for_exit 7200; then
  capture_screen "$WORK_DIR/install-timeout.ppm"
  echo "Spider OS installer did not power off within 120 minutes." >&2
  tail -n 300 "$INSTALL_SERIAL" >&2 || true
  exit 1
fi

rm -f "$PIDFILE" "$MONITOR"

if grep -Eqi 'Traceback|autoinstall.*error|curtin.*failed|installation failed|kernel panic' "$INSTALL_SERIAL"; then
  echo "Installer log contains a fatal condition." >&2
  tail -n 400 "$INSTALL_SERIAL" >&2
  exit 1
fi

echo "[qualification] installation completed; booting only from installed disk"
qemu-system-x86_64 \
  -machine q35 \
  "${accel[@]}" \
  -m 6144 \
  -smp 4 \
  -boot order=c \
  -drive "file=$DISK,format=qcow2,if=virtio,cache=unsafe" \
  -device virtio-vga \
  -display none \
  -serial "file:$BOOT_SERIAL" \
  -monitor "unix:$MONITOR,server=on,wait=off" \
  -pidfile "$PIDFILE" \
  -daemonize

for _ in $(seq 1 120); do
  if grep -Fq 'SPIDER_QUALIFICATION_READY' "$BOOT_SERIAL" 2>/dev/null; then
    echo "Spider OS installed-system qualification passed."
    capture_screen "$WORK_DIR/installed-ready.ppm"
    exit 0
  fi
  if grep -Fq 'SPIDER_QUALIFICATION_FAILED:' "$BOOT_SERIAL" 2>/dev/null; then
    capture_screen "$WORK_DIR/installed-failed.ppm"
    echo "Spider OS installed-system qualification reported failure." >&2
    tail -n 400 "$BOOT_SERIAL" >&2 || true
    exit 1
  fi
  sleep 10
done

capture_screen "$WORK_DIR/installed-timeout.ppm"
echo "Installed Spider OS did not become ready within 20 minutes." >&2
tail -n 400 "$BOOT_SERIAL" >&2 || true
exit 1
