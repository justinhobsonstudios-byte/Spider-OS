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
  ostree \
  podman \
  python3 \
  qt6-qtdeclarative \
  qt6-qtdeclarative-devel \
  qt6-qtwayland

# Install the native RPM build of VS Code. Keeping the repository definition
# in the image lets normal dnf/rpm tooling repair or update Code in writable
# mode instead of relying on a browser launcher or a per-user download.
rpm --import https://packages.microsoft.com/keys/microsoft.asc
install -d -m 0755 /etc/yum.repos.d
install -m 0644 /ctx/system_files/etc/yum.repos.d/vscode.repo \
  /etc/yum.repos.d/vscode.repo
dnf5 install -y code

# Fedora names the Qt 6 QML runner qml-qt6. Validate the exact executable that
# spider-os-open launches so CI catches a broken native shell before ISO build.
command -v qml-qt6 >/dev/null
command -v code >/dev/null

chmod 0755 \
  /usr/bin/spider-os \
  /usr/bin/spider-os-open \
  /usr/bin/spider-os-writable-root \
  /usr/bin/spider-searxng-prepare \
  /usr/bin/spider-os-first-login \
  /usr/bin/spider-hardware-report \
  /usr/bin/spider-security-lab

systemctl --global enable spider-os.service
systemctl --global enable spider-searxng.service
systemctl --global enable spider-ai-resident.service
systemctl enable spider-os-writable-root.service
dnf5 clean all
