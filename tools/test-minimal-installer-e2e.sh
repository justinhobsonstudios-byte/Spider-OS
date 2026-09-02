#!/usr/bin/env bash
set -euo pipefail

[ "$#" -ge 1 ] && [ "$#" -le 2 ] || {
  echo "usage: $0 <installer.iso> [evidence-directory]" >&2
  exit 2
}

iso="$(realpath "$1")"
evidence="${2:-$(pwd)/iso-e2e-evidence}"
test -f "$iso"
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
  local monitor="$1" target="$2" ppm="${2%.png}.ppm"
  [ -S "$monitor" ] || return 0
  printf 'screendump %s\n' "$ppm" | socat - "UNIX-CONNECT:$monitor" >/dev/null 2>&1 || return 0
  [ -s "$ppm" ] || return 0
  convert "$ppm" "$target" >/dev/null 2>&1 || return 0
  rm -f "$ppm"
}
wait_monitor() {
  for _ in $(seq 1 30); do
    [ -S "$1" ] && return 0
    sleep 1
  done
  return 1
}

for command in convert curl openssl qemu-img qemu-system-x86_64 realpath socat ssh ssh-keygen xorriso; do
  command -v "$command" >/dev/null
done

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

mkdir -p "$workdir/kickstart"
cat > "$workdir/kickstart/spider-ci.ks" <<KICKSTART
%include /run/install/repo/osbuild-base.ks
text --non-interactive
firewall --enabled --service=ssh
services --enabled=NetworkManager,sshd
user --name=spiderci --groups=wheel --password='${password_hash}' --iscrypted
sshkey --username=spiderci "${ssh_public_key}"
zerombr
autopart --noswap --type=btrfs
reboot
%post --log=/root/spider-ci-post.log
install -d -m 0750 /etc/sudoers.d
echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/99-spider-ci
chmod 0440 /etc/sudoers.d/99-spider-ci
touch /etc/spider-ci-installed
%end
KICKSTART

python3 -m http.server 18080 --bind 0.0.0.0 --directory "$workdir/kickstart"   > "$evidence/kickstart-http.log" 2>&1 &
http_pid="$!"
curl --retry 10 --retry-delay 1 --fail --silent   http://127.0.0.1:18080/spider-ci.ks >/dev/null

accel=(-accel 'tcg,thread=multi' -cpu max)
install_timeout=7200
boot_timeout=2400
if [ -c /dev/kvm ]; then
  sudo chmod 666 /dev/kvm >/dev/null 2>&1 || true
fi
if [ -c /dev/kvm ] && [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
  accel=(-accel kvm -cpu host)
  install_timeout=3600
  boot_timeout=1200
fi

disk="$workdir/spider-installed.qcow2"
qemu-img create -f qcow2 "$disk" 40G >/dev/null
install_monitor="$workdir/install-monitor.sock"
qemu-system-x86_64 -machine q35 "${accel[@]}" -m 6144 -smp 2   -kernel "$kernel" -initrd "$initrd"   -append "inst.stage2=hd:LABEL=SPIDER_OS inst.ks=http://10.0.2.2:18080/spider-ci.ks ip=dhcp rd.neednet=1 inst.noninteractive console=tty0 console=ttyS0,115200n8"   -drive "file=$disk,format=qcow2,if=virtio"   -drive "file=$iso,media=cdrom,readonly=on"   -netdev user,id=installnet -device virtio-net-pci,netdev=installnet   -display none -monitor "unix:$install_monitor,server=on,wait=off"   -serial "file:$evidence/installer-serial.log" -no-reboot   -daemonize -pidfile "$workdir/install.pid"

wait_monitor "$install_monitor"
install_pid="$(cat "$workdir/install.pid")"
started="$SECONDS"
while kill -0 "$install_pid" >/dev/null 2>&1; do
  if [ $((SECONDS - started)) -ge "$install_timeout" ]; then
    capture_screen "$install_monitor" "$evidence/install-timeout.png"
    echo "Installer did not complete in ${install_timeout}s." >&2
    exit 1
  fi
  sleep 10
done
install_pid=""

grep -Eq 'anaconda .* started\.' "$evidence/installer-serial.log"
if grep -Eqi 'installation failed|kickstart.*(error|failed)|error enabling service|installer will now terminate|traceback|kernel panic|dracut.*emergency' "$evidence/installer-serial.log"; then
  echo "Fatal installer condition found." >&2
  exit 1
fi
grep -Fq 'reboot: Restarting system' "$evidence/installer-serial.log" || {
  echo "Anaconda did not complete the install-and-reboot lifecycle." >&2
  exit 1
}
qemu-img info "$disk" > "$evidence/installed-disk.txt"

installed_monitor="$workdir/installed-monitor.sock"
qemu-system-x86_64 -machine q35 "${accel[@]}" -m 6144 -smp 2   -boot order=c -drive "file=$disk,format=qcow2,if=virtio"   -netdev "user,id=installednet,hostfwd=tcp:127.0.0.1:22222-:22"   -device virtio-net-pci,netdev=installednet   -display none -monitor "unix:$installed_monitor,server=on,wait=off"   -serial "file:$evidence/installed-serial.log"   -daemonize -pidfile "$workdir/installed.pid"

wait_monitor "$installed_monitor"
installed_pid="$(cat "$workdir/installed.pid")"
ssh_args=(-i "$ssh_key" -p 22222 -o BatchMode=yes -o ConnectTimeout=5   -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null spiderci@127.0.0.1)

boot_started="$SECONDS"
ssh_ready=0
while [ $((SECONDS - boot_started)) -lt "$boot_timeout" ]; do
  kill -0 "$installed_pid" >/dev/null 2>&1 || break
  if ssh "${ssh_args[@]}" true >/dev/null 2>&1; then
    ssh_ready=1
    break
  fi
  sleep 10
done
[ "$ssh_ready" -eq 1 ] || {
  capture_screen "$installed_monitor" "$evidence/ssh-timeout.png"
  echo "Installed disk never became reachable over SSH." >&2
  exit 1
}

graphical_ready=0
while [ $((SECONDS - boot_started)) -lt "$boot_timeout" ]; do
  if ssh "${ssh_args[@]}" '
    test "$(systemctl get-default)" = graphical.target &&
    sudo systemctl is-active --quiet graphical.target &&
    sudo systemctl is-active --quiet display-manager.service &&
    sudo systemctl is-active --quiet plasmalogin.service &&
    test "$(sudo systemctl show -p Id --value display-manager.service)" = plasmalogin.service &&
    test -f /usr/share/wayland-sessions/plasma.desktop
  ' >/dev/null 2>&1; then
    graphical_ready=1
    break
  fi
  sleep 10
done

diagnostics() {
  ssh "${ssh_args[@]}" 'set +e
    echo "=== milestone ==="
    test -f /etc/spider-ci-installed && echo "PASS: installed marker"
    echo "default target: $(systemctl get-default)"
    echo "display manager: $(sudo systemctl show -p Id --value display-manager.service)"
    echo
    sudo systemctl --no-pager --full status graphical.target display-manager.service plasmalogin.service
    echo
    sudo journalctl -b -u plasmalogin.service --no-pager -n 200
    echo
    ls -la /usr/share/wayland-sessions /usr/share/xsessions 2>/dev/null
    echo
    sudo bootc status
  ' 2>&1
}

[ "$graphical_ready" -eq 1 ] || {
  capture_screen "$installed_monitor" "$evidence/graphical-timeout.png"
  diagnostics > "$evidence/installed-diagnostics.txt" || true
  cat "$evidence/installed-diagnostics.txt" >&2
  exit 1
}

capture_screen "$installed_monitor" "$evidence/kde-login-ready.png"
diagnostics > "$evidence/installed-verification.txt"
test -s "$evidence/kde-login-ready.png"
colors="$(identify -format '%k' "$evidence/kde-login-ready.png")"
[ "$colors" -gt 16 ] || {
  echo "Graphical target is active, but the captured login screen has only $colors colors." >&2
  exit 1
}
printf 'PASS: production ISO installed to blank disk, rebooted disk-only, and reached Plasma Login Manager (%s colors).\n' "$colors"   | tee -a "$evidence/installed-verification.txt"
