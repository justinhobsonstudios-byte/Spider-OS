#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/upstream.env"

WORK_DIR="${SPIDER_BUILD_WORK_DIR:-$REPO_ROOT/.cache/spider-os/ubuntu-foundation}"
OUTPUT_DIR="${SPIDER_OUTPUT_DIR:-$REPO_ROOT/out}"
OUTPUT_ISO="${SPIDER_OUTPUT_ISO:-$OUTPUT_DIR/Spider_OS_1.0_amd64.iso}"
UPSTREAM_ISO="$WORK_DIR/$SPIDER_UPSTREAM_ISO"
TOOLS_DIR="$WORK_DIR/tools"
LIVEFS_DIR="$TOOLS_DIR/livefs-editor"
VENV_DIR="$TOOLS_DIR/livefs-editor-venv"
ACTIONS_FILE="$WORK_DIR/spider-livefs-actions.yaml"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 2
  }
}

for cmd in curl git python3 sha256sum xorriso unsquashfs mksquashfs; do
  need "$cmd"
done

mkdir -p "$WORK_DIR" "$OUTPUT_DIR" "$TOOLS_DIR"

if [[ ! -f "$UPSTREAM_ISO" ]]; then
  echo "Downloading $SPIDER_UPSTREAM_ISO"
  curl --fail --location --retry 4 --retry-delay 3 \
    --continue-at - \
    "$SPIDER_UPSTREAM_URL" \
    --output "$UPSTREAM_ISO"
fi

printf '%s  %s\n' "$SPIDER_UPSTREAM_SHA256" "$UPSTREAM_ISO" | sha256sum --check --strict

if [[ ! -d "$LIVEFS_DIR/.git" ]]; then
  rm -rf "$LIVEFS_DIR"
  git clone "$LIVEFS_EDITOR_REPO" "$LIVEFS_DIR"
fi

git -C "$LIVEFS_DIR" fetch --quiet origin "$LIVEFS_EDITOR_COMMIT"
git -C "$LIVEFS_DIR" checkout --quiet --detach "$LIVEFS_EDITOR_COMMIT"

if [[ ! -x "$VENV_DIR/bin/livefs-edit" ]]; then
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --disable-pip-version-check --quiet "$LIVEFS_DIR"
fi

cat >"$ACTIONS_FILE" <<YAML
---
- name: setup-rootfs
  target: rootfs

- name: shell
  command: |
    set -eux
    cp -a "$REPO_ROOT/distro/overlay/." rootfs/
    install -D -m 0644 "$REPO_ROOT/web/workspaces/workspaces.yaml" rootfs/usr/share/spider-os/workspaces/workspaces.yaml
    install -D -m 0644 "$REPO_ROOT/distro/manifests/default-apps.yaml" rootfs/usr/share/spider-os/manifests/default-apps.yaml

    chmod 0755 rootfs/usr/lib/spider-os/bin/spider-weave
    chmod 0755 rootfs/usr/lib/spider-os/bin/spider-webbie
    chmod 0755 rootfs/usr/lib/spider-os/bin/spider-forage
    chmod 0755 rootfs/usr/lib/spider-os/bin/spider-session-init
    chmod 0755 rootfs/usr/lib/spider-os/bin/spider-foundation-verify

    mkdir -p rootfs/etc/systemd/system/multi-user.target.wants
    ln -sfn /usr/lib/systemd/system/spider-weave.service rootfs/etc/systemd/system/multi-user.target.wants/spider-weave.service
    ln -sfn /usr/lib/systemd/system/spider-qualification.service rootfs/etc/systemd/system/multi-user.target.wants/spider-qualification.service

    mkdir -p rootfs/etc/systemd/user/default.target.wants
    ln -sfn /usr/lib/systemd/user/spider-webbie.service rootfs/etc/systemd/user/default.target.wants/spider-webbie.service
    ln -sfn /usr/lib/systemd/user/spider-forage.service rootfs/etc/systemd/user/default.target.wants/spider-forage.service

- name: add-cmdline-arg
  arg: spider.live=1
  persist: false

- name: add-xorriso-args
  xorriso_args:
    - -volid
    - SPIDER_OS
YAML

rm -f "$OUTPUT_ISO"

echo "Building Spider OS $SPIDER_VERSION from Ubuntu Studio $SPIDER_UPSTREAM_VERSION"
sudo "$VENV_DIR/bin/livefs-edit" \
  "$UPSTREAM_ISO" \
  "$OUTPUT_ISO" \
  --action-yaml "$ACTIONS_FILE"

[[ -s "$OUTPUT_ISO" ]]
sha256sum "$OUTPUT_ISO" >"$OUTPUT_ISO.sha256"

xorriso -indev "$OUTPUT_ISO" -pvd_info 2>&1 | tee "$WORK_DIR/pvd-info.txt"
grep -Fq "Volume id    : 'SPIDER_OS'" "$WORK_DIR/pvd-info.txt"

cat <<EOF
Spider OS ISO built successfully.
ISO: $OUTPUT_ISO
SHA256: $OUTPUT_ISO.sha256
Upstream: $SPIDER_UPSTREAM_ISO
EOF
