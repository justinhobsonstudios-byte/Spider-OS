#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <Spider_OS.iso> <qualification.iso>" >&2
  exit 2
fi

SOURCE_ISO="$(readlink -f "$1")"
OUTPUT_ISO="$(readlink -m "$2")"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/upstream.env"

WORK_DIR="${SPIDER_BUILD_WORK_DIR:-$REPO_ROOT/.cache/spider-os/ubuntu-foundation}"
LIVEFS_DIR="$WORK_DIR/tools/livefs-editor"
VENV_DIR="$WORK_DIR/tools/livefs-editor-venv"
AUTOINSTALL="$REPO_ROOT/tests/installed-system/autoinstall.yaml"
ACTIONS="$WORK_DIR/qualification-actions.yaml"

[[ -f "$SOURCE_ISO" ]] || { echo "Source ISO not found: $SOURCE_ISO" >&2; exit 2; }
[[ -f "$AUTOINSTALL" ]] || { echo "Autoinstall config not found: $AUTOINSTALL" >&2; exit 2; }

if [[ ! -x "$VENV_DIR/bin/livefs-edit" ]]; then
  mkdir -p "$WORK_DIR/tools"
  if [[ ! -d "$LIVEFS_DIR/.git" ]]; then
    git clone "$LIVEFS_EDITOR_REPO" "$LIVEFS_DIR"
  fi
  git -C "$LIVEFS_DIR" fetch --quiet origin "$LIVEFS_EDITOR_COMMIT"
  git -C "$LIVEFS_DIR" checkout --quiet --detach "$LIVEFS_EDITOR_COMMIT"
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --disable-pip-version-check --quiet "$LIVEFS_DIR"
fi

cat >"$ACTIONS" <<YAML
---
- name: add-autoinstall-config
  autoinstall_config: "$AUTOINSTALL"

- name: add-cmdline-arg
  arg: spider.qualification=1
  persist: true

- name: add-cmdline-arg
  arg: console=ttyS0,115200n8
  persist: true

- name: add-cmdline-arg
  arg: systemd.show_status=true
  persist: true
YAML

rm -f "$OUTPUT_ISO"
sudo "$VENV_DIR/bin/livefs-edit" \
  "$SOURCE_ISO" \
  "$OUTPUT_ISO" \
  --action-yaml "$ACTIONS"

[[ -s "$OUTPUT_ISO" ]]
echo "Qualification ISO: $OUTPUT_ISO"
