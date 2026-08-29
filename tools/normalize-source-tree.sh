#!/usr/bin/env bash
set -euo pipefail

archive="${GITHUB_WORKSPACE:-$PWD}/Spider_OS_v0.7_GitHub_ISO_Ready.zip"
test -f "$archive"

work_root="${RUNNER_TEMP:-/tmp}/spider-os-source-normalization"
rm -rf "$work_root"
mkdir -p "$work_root"
unzip -q "$archive" -d "$work_root"

legacy_root=""
while IFS= read -r containerfile; do
  candidate="$(dirname "$containerfile")"
  if [ -d "$candidate/build_files" ] && \
     [ -d "$candidate/system_files" ] && \
     [ -d "$candidate/src/spider_os" ]; then
    legacy_root="$candidate"
    break
  fi
done < <(find "$work_root" -type f -name Containerfile -print)

if [ -z "$legacy_root" ]; then
  echo "Legacy archive does not contain the expected Spider OS image-template tree." >&2
  exit 1
fi

rm -rf build_files system_files src tests
cp -a "$legacy_root/build_files" ./build_files
cp -a "$legacy_root/system_files" ./system_files
mkdir -p src tests
cp -a "$legacy_root/src/spider_os" ./src/spider_os

# Overlay the newer flattened sources. The archive is recovery material only.
install -m 0755 build.sh build_files/build.sh

python_sources=(
  __init__.py __main__.py actions.py ai.py authority.py cli.py constants.py
  db.py learning.py personal_web.py preload.py proactive.py research.py resident.py
  screen_context.py server.py
)
for file in "${python_sources[@]}"; do
  test -f "$file"
  install -m 0644 "$file" "src/spider_os/$file"
done

install -d -m 0755 src/spider_os/data src/spider_os/web/assets
install -m 0644 preload_knowledge.json src/spider_os/data/preload_knowledge.json
for file in app.js index.html manifest.webmanifest styles.css sw.js; do
  install -m 0644 "$file" "src/spider_os/web/$file"
done
install -m 0644 spider-mark.svg src/spider_os/web/assets/spider-mark.svg
if [ -f spider-original-crimson-distressed.png ]; then
  install -m 0644 spider-original-crimson-distressed.png \
    src/spider_os/web/assets/spider-original-crimson-distressed.png
fi

install -d -m 0755 \
  system_files/usr/bin \
  system_files/usr/lib/systemd/user \
  system_files/usr/share/applications \
  system_files/etc/xdg/autostart

for file in spider-os spider-os-open spider-os-first-login spider-hardware-report spider-security-lab; do
  install -m 0755 "$file" "system_files/usr/bin/$file"
done
for file in spider-os.service spider-ai-resident.service; do
  install -m 0644 "$file" "system_files/usr/lib/systemd/user/$file"
done
for file in spider-os.desktop spider-hardware-report.desktop spider-security-lab.desktop; do
  install -m 0644 "$file" "system_files/usr/share/applications/$file"
done
for file in spider-os-autostart.desktop spider-os-first-login.desktop; do
  install -m 0644 "$file" "system_files/etc/xdg/autostart/$file"
done

python3 - <<'PY'
from pathlib import Path
import re

service = Path("system_files/usr/lib/systemd/user/spider-ai-resident.service")
text = service.read_text(encoding="utf-8")
replacement = 'Environment="SPIDER_AI_WAKE_PHRASES=Hey Webbie;Webbie;Hey Web;Web"'
updated, count = re.subn(r"^Environment=.*$", replacement, text, count=1, flags=re.M)
if count != 1:
    raise SystemExit("Could not update Webbie wake phrases in canonical service")
service.write_text(updated, encoding="utf-8")
PY

for file in test_*.py; do
  [ -f "$file" ] || continue
  install -m 0644 "$file" "tests/$file"
done

git rm -f --ignore-unmatch \
  __init__.py __main__.py actions.py ai.py authority.py cli.py constants.py \
  db.py learning.py personal_web.py preload.py proactive.py research.py resident.py \
  screen_context.py server.py preload_knowledge.json app.js index.html \
  manifest.webmanifest styles.css sw.js spider-mark.svg build.sh \
  spider-os spider-os-open spider-os-first-login spider-hardware-report \
  spider-security-lab spider-os.service spider-ai-resident.service \
  spider-os-autostart.desktop spider-os-first-login.desktop \
  spider-hardware-report.desktop spider-os.desktop spider-security-lab.desktop \
  test_*.py test_database.py.tmp PKG-INFO dependency_links.txt entry_points.txt \
  top_level.txt SOURCES.txt spider-os.dat spider-original-crimson-distressed.png \
  Spider_OS_v0.7_GitHub_ISO_Ready.zip

# Structural and behavioral validation.
test -f docs/BRAND.md
test -f docs/NAMING.md
test -f build_files/build.sh
test -x build_files/build.sh
test -f system_files/usr/share/wallpapers/SpiderOS/contents/images/1920x1080.svg
test -f system_files/usr/share/sounds/SpiderOS/stereo/spider-ai-ready.wav
test -f src/spider_os/resident.py
test -f src/spider_os/web/assets/spider-mark.svg
grep -Fq 'Hey Webbie;Webbie;Hey Web;Web' \
  system_files/usr/lib/systemd/user/spider-ai-resident.service
! test -e resident.py
! test -e Spider_OS_v0.7_GitHub_ISO_Ready.zip

bash -n build_files/build.sh
python3 -m compileall -q src/spider_os
python3 -m pytest -q

# Validation creates bytecode caches; keep generated files out of source control.
find src tests -type d -name __pycache__ -prune -exec rm -rf {} +
find src tests -type f -name '*.pyc' -delete
