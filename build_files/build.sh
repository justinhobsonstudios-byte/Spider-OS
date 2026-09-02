#!/usr/bin/env bash
set -ouex pipefail

# Keep milestone 1 deliberately small: use Aurora's shipped KDE stack and add
# only Spider OS branding. The application stack returns after the installed
# graphical system has proved itself.
cp -avf /ctx/system_files/. /

systemctl set-default graphical.target
systemctl enable plasmalogin.service

test "$(readlink -f /etc/systemd/system/default.target)" =   /usr/lib/systemd/system/graphical.target
test -e /etc/systemd/system/display-manager.service
systemctl is-enabled plasmalogin.service

dnf5 clean all
