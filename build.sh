#!/usr/bin/env bash
set -ouex pipefail

cp -avf /ctx/system_files/. /

install -d -m 0755 /usr/lib/spider-os
cp -avf /ctx/spider_os /usr/lib/spider-os/

install -d -m 0755 /usr/share/icons/hicolor/scalable/apps
install -m 0644 /ctx/spider_os/web/assets/spider-mark.svg \
  /usr/share/icons/hicolor/scalable/apps/spider-os.svg

dnf5 install -y \
  curl \
  distrobox \
  podman \
  python3 \
  pipewire-jack-audio-connection-kit \
  qpwgraph \
  rtkit

chmod 0755 \
  /usr/bin/spider-os \
  /usr/bin/spider-os-open \
  /usr/bin/spider-os-first-login \
  /usr/bin/spider-hardware-report \
  /usr/bin/spider-creative-pack \
  /usr/bin/spider-security-lab

systemctl --global enable spider-os.service
systemctl --global enable spider-ai-resident.service
dnf5 clean all
