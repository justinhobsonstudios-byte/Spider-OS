#!/usr/bin/env bash
set -euo pipefail

workspace="${1:?workspace required}"
project_root="${2:?project root required}"
overrides="$workspace/overrides"

if [ ! -d "$overrides" ]; then
  echo "No Spider OS source overrides found."
  exit 0
fi

# The historical v0.7 upload contains the real image-template tree inside a ZIP.
# Overlay current text-source work onto that extracted tree until the archive is
# retired. This keeps new development reviewable in Git instead of hiding it in
# another binary archive.
cp -av "$overrides"/. "$project_root"/

echo "Applied Spider OS source overrides to: $project_root"
