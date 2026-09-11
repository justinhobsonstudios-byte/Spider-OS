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
  python3

chmod 0755 \
  /usr/bin/spider-os \
  /usr/bin/spider-os-open \
  /usr/bin/spider-os-first-login \
  /usr/bin/spider-hardware-report \
  /usr/bin/spider-security-lab \
  /usr/libexec/spider-os-session-bootstrap

# The installed image must boot to KDE. Aurora 44 uses Plasma Login Manager;
# keep older Aurora images usable when they still ship SDDM.
if [ -f /usr/lib/systemd/system/plasmalogin.service ]; then
  display_manager=plasmalogin.service
elif [ -f /usr/lib/systemd/system/sddm.service ]; then
  display_manager=sddm.service
else
  echo 'No supported KDE display manager is installed.' >&2
  exit 1
fi
systemctl enable --force "$display_manager"
systemctl set-default graphical.target

# The Web core and Webbie are ordinary user services. KDE owns session assembly
# through one autostart bridge; do not create a second systemd assembly path.
systemctl --global enable spider-os.service
systemctl --global enable spider-ai-resident.service

dnf5 clean all
