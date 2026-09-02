#!/usr/bin/env bash
set -ouex pipefail

# Keep milestone 1 deliberately small: use Aurora's shipped KDE stack and add
# only Spider OS branding. The application stack returns after the installed
# graphical system has proved itself.
cp -avf /ctx/system_files/. /

# bootc treats /usr as image-owned content while /etc is mutable machine state.
# A build-time set-default writes only to /etc, which does not reliably become
# the installed system's default. Ship the default-target alias with the image
# and remove any transient build-container override.
ln -sfn graphical.target /usr/lib/systemd/system/default.target
rm -f /etc/systemd/system/default.target
systemctl enable plasmalogin.service

test "$(readlink /usr/lib/systemd/system/default.target)" = graphical.target
test ! -e /etc/systemd/system/default.target
test -e /etc/systemd/system/display-manager.service
systemctl is-enabled plasmalogin.service

dnf5 clean all
