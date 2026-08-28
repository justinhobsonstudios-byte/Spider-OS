#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 <Spider_OS_x86_64.iso> [evidence-directory]" >&2
  exit 2
}

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage

iso="$(realpath "$1")"
evidence="${2:-$(pwd)/iso-e2e-evidence}"

[ -f "$iso" ] || {
  echo "installer ISO not found: $iso" >&2
  exit 1
}

for command in \
  convert curl openssl python3 qemu-img qemu-system-x86_64 \
  realpath socat ssh ssh-keygen xorriso; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "required command not found: $command" >&2
    exit 1
  }
done

mkdir -p "$evidence"
workdir="$(mktemp -d)"
install_pid=""
installed_pid=""
http_pid=""

stop_pid() {
  local pid="${1:-}"
  if [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do
      kill -0 "$pid" >/dev/null 2>&1 || return 0
      sleep 1
    done
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi
}

cleanup() {
  stop_pid "$installed_pid"
  stop_pid "$install_pid"
  stop_pid "$http_pid"
  rm -rf "$workdir"
}
trap cleanup EXIT INT TERM

capture_screen() {
  local monitor="$1"
  local target="$2"
  [ -S "$monitor" ] || return 0
  local ppm="${target%.png}.ppm"
  printf 'screendump %s\n' "$ppm" | socat - "UNIX-CONNECT:$monitor" >/dev/null 2>&1 || return 0
  [ -s "$ppm" ] || return 0
  convert "$ppm" "$target" >/dev/null 2>&1 || return 0
  rm -f "$ppm"
}

wait_for_monitor() {
  local monitor="$1"
  for _ in $(seq 1 30); do
    [ -S "$monitor" ] && return 0
    sleep 1
  done
  echo "QEMU monitor did not become ready: $monitor" >&2
  return 1
}

# The ISO must remain the real production artifact. CI supplies only temporary
# install answers and a disposable login key; neither is copied into the ISO.
kernel="$workdir/vmlinuz"
initrd="$workdir/initrd.img"
xorriso -osirrox on -indev "$iso" -extract /images/pxeboot/vmlinuz "$kernel" >/dev/null 2>&1
xorriso -osirrox on -indev "$iso" -extract /images/pxeboot/initrd.img "$initrd" >/dev/null 2>&1
test -s "$kernel"
test -s "$initrd"

ssh_key="$workdir/spider-ci-key"
ssh-keygen -q -t ed25519 -N '' -f "$ssh_key"
ssh_public_key="$(cat "$ssh_key.pub")"
password_hash="$(openssl passwd -6 "$(openssl rand -hex 24)")"

kickstart_root="$workdir/kickstart"
mkdir -p "$kickstart_root"
cat > "$kickstart_root/spider-ci.ks" <<KICKSTART
%include /run/install/repo/osbuild-base.ks

graphical
firewall --enabled --service=ssh
services --enabled=NetworkManager,sshd,sddm

user --name=spiderci --groups=wheel --password='${password_hash}' --iscrypted
sshkey --username=spiderci "${ssh_public_key}"

zerombr
autopart --noswap --type=btrfs
reboot

%post --log=/root/spider-ci-post.log
install -d -m 0755 /etc/sddm.conf.d
cat > /etc/sddm.conf.d/99-spider-ci-autologin.conf <<'SDDM'
[Autologin]
User=spiderci
Session=plasma
Relogin=false
SDDM
install -d -m 0750 /etc/sudoers.d
echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/99-spider-ci
chmod 0440 /etc/sudoers.d/99-spider-ci
touch /etc/spider-ci-installed
%end
KICKSTART

# QEMU user networking exposes the host at 10.0.2.2. Serving the kickstart keeps
# the production ISO unchanged while exercising its exact kernel, initramfs,
# Anaconda runtime, embedded container payload, and repaired product metadata.
http_port=18080
python3 -m http.server "$http_port" --bind 0.0.0.0 --directory "$kickstart_root" \
  > "$evidence/kickstart-http.log" 2>&1 &
http_pid="$!"
sleep 1
curl --fail --silent "http://127.0.0.1:${http_port}/spider-ci.ks" >/dev/null

accel_args=(-accel 'tcg,thread=multi' -cpu max)
accel_name='tcg,thread=multi'
install_timeout=7200
first_login_timeout=2400
if [ -c /dev/kvm ]; then
  sudo chmod 666 /dev/kvm >/dev/null 2>&1 || true
fi
if [ -c /dev/kvm ] && [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
  accel_args=(-accel kvm -cpu host)
  accel_name='kvm'
  install_timeout=3600
  first_login_timeout=1200
fi
echo "QEMU acceleration: $accel_name" | tee "$evidence/acceleration.txt"

disk="$workdir/spider-installed.qcow2"
qemu-img create -f qcow2 "$disk" 40G >/dev/null

install_monitor="$workdir/install-monitor.sock"
install_pidfile="$workdir/install.pid"
install_serial="$evidence/installer-serial.log"

qemu-system-x86_64 \
  -machine q35 \
  "${accel_args[@]}" \
  -m 6144 \
  -smp 2 \
  -kernel "$kernel" \
  -initrd "$initrd" \
  -append "inst.stage2=hd:LABEL=SPIDER_OS inst.ks=http://10.0.2.2:${http_port}/spider-ci.ks ip=dhcp rd.neednet=1 inst.noninteractive console=tty0 console=ttyS0,115200n8" \
  -drive "file=$disk,format=qcow2,if=virtio" \
  -drive "file=$iso,media=cdrom,readonly=on" \
  -netdev user,id=installnet \
  -device virtio-net-pci,netdev=installnet \
  -display none \
  -monitor "unix:$install_monitor,server=on,wait=off" \
  -serial "file:$install_serial" \
  -no-reboot \
  -daemonize \
  -pidfile "$install_pidfile"

wait_for_monitor "$install_monitor"
install_pid="$(cat "$install_pidfile")"
install_started="$SECONDS"
next_capture=60
capture_index=0

while kill -0 "$install_pid" >/dev/null 2>&1; do
  elapsed=$((SECONDS - install_started))
  if [ "$elapsed" -ge "$next_capture" ]; then
    capture_index=$((capture_index + 1))
    capture_screen "$install_monitor" "$evidence/install-${capture_index}-${elapsed}s.png"
    next_capture=$((next_capture + 120))
  fi
  if [ "$elapsed" -ge "$install_timeout" ]; then
    capture_screen "$install_monitor" "$evidence/install-timeout.png"
    echo "Anaconda did not reboot within ${install_timeout}s." >&2
    exit 1
  fi
  sleep 10
done
install_pid=""

grep -Fq 'Install finished' "$install_serial" || {
  echo "Anaconda rebooted without emitting the bootc install completion marker." >&2
  exit 1
}
if grep -Eqi 'installation failed|kickstart.*(error|failed)|traceback|kernel panic|dracut.*emergency' "$install_serial"; then
  echo "Fatal installer condition found in serial output." >&2
  exit 1
fi

qemu-img info "$disk" | tee "$evidence/installed-disk.txt"

# Boot only the installed disk. SSH proves the deployed OS reached userspace;
# SDDM autologin then exercises the real KDE autostart entries used by Cory.
installed_monitor="$workdir/installed-monitor.sock"
installed_pidfile="$workdir/installed.pid"
installed_serial="$evidence/installed-serial.log"
ssh_port=22222

qemu-system-x86_64 \
  -machine q35 \
  "${accel_args[@]}" \
  -m 6144 \
  -smp 2 \
  -boot order=c \
  -drive "file=$disk,format=qcow2,if=virtio" \
  -netdev "user,id=installednet,hostfwd=tcp:127.0.0.1:${ssh_port}-:22" \
  -device virtio-net-pci,netdev=installednet \
  -display none \
  -monitor "unix:$installed_monitor,server=on,wait=off" \
  -serial "file:$installed_serial" \
  -daemonize \
  -pidfile "$installed_pidfile"

wait_for_monitor "$installed_monitor"
installed_pid="$(cat "$installed_pidfile")"

ssh_args=(
  -i "$ssh_key"
  -p "$ssh_port"
  -o BatchMode=yes
  -o ConnectTimeout=5
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  spiderci@127.0.0.1
)

boot_started="$SECONDS"
ssh_ready=0
while [ $((SECONDS - boot_started)) -lt "$first_login_timeout" ]; do
  if ! kill -0 "$installed_pid" >/dev/null 2>&1; then
    echo "Installed Spider OS VM stopped before SSH became ready." >&2
    exit 1
  fi
  if ssh "${ssh_args[@]}" true >/dev/null 2>&1; then
    ssh_ready=1
    break
  fi
  sleep 10
done
[ "$ssh_ready" -eq 1 ] || {
  capture_screen "$installed_monitor" "$evidence/installed-ssh-timeout.png"
  echo "Installed Spider OS never became reachable over SSH." >&2
  exit 1
}

assembly_ready=0
while [ $((SECONDS - boot_started)) -lt "$first_login_timeout" ]; do
  if ssh "${ssh_args[@]}" \
    'test -f "$HOME/.config/spider-os/desktop-initialized" &&
     test -f "$HOME/.config/spider-os/session-opened" &&
     curl --fail --silent --max-time 3 http://127.0.0.1:8765/api/health >/dev/null' \
     >/dev/null 2>&1; then
    assembly_ready=1
    break
  fi
  sleep 10
done
[ "$assembly_ready" -eq 1 ] || {
  capture_screen "$installed_monitor" "$evidence/web-assembly-timeout.png"
  ssh "${ssh_args[@]}" 'systemctl --user --no-pager --full status spider-os.service spider-ai-resident.service || true' \
    > "$evidence/web-assembly-status.txt" 2>&1 || true
  echo "Installed Spider OS booted, but Web Assembly did not complete." >&2
  exit 1
}

ssh "${ssh_args[@]}" '
  set -eu
  test -f /etc/spider-ci-installed
  test -x /usr/bin/spider-os
  test -x /usr/bin/spider-os-first-login
  systemctl --user is-active spider-os.service
  systemctl --user is-active spider-ai-resident.service
  curl --fail --silent --max-time 3 http://127.0.0.1:8765/api/health
  sudo bootc status
' > "$evidence/installed-verification.txt"

capture_screen "$installed_monitor" "$evidence/web-assembly-ready.png"
printf 'info status\n' | socat - "UNIX-CONNECT:$installed_monitor" \
  > "$evidence/installed-qemu-status.txt"
grep -Fq 'VM status: running' "$evidence/installed-qemu-status.txt"

echo "PASS: ISO installed Spider OS, rebooted from disk, logged into KDE, and completed Web Assembly."
