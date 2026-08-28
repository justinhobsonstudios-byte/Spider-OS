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
  pciutils \
  usbutils \
  python3-pocketsphinx \
  pocketsphinx-models \
  python3-sounddevice \
  speech-dispatcher \
  speech-dispatcher-espeak-ng

chmod 0755 \
  /usr/bin/spider-os \
  /usr/bin/spider-os-open \
  /usr/bin/spider-os-first-login \
  /usr/bin/spider-webbie-resident \
  /usr/bin/spider-hardware-report \
  /usr/bin/spider-security-lab \
  /usr/libexec/spider-os-privileged-control

chmod 0644 /usr/share/polkit-1/actions/com.spideros.control.policy

systemctl --global enable spider-os.service
systemctl --global enable spider-web-assembly.service
systemctl --global enable spider-ai-resident.service
systemctl --global enable spider-webbie-voice.service

dnf5 clean all
