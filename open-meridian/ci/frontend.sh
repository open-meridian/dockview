#!/bin/bash
# The desk's front end, built for the plugin's image into
# open-meridian/plugin/web: the pinned packages installed from
# web/package-lock.json, type-checked and bundled (web/build.mjs); then the
# notices of every package it ships, refused if any is under a GPL-family
# licence or is dockview-enterprise; and the files bundled (web/bundled.json)
# searched for dockview-enterprise.
#
# Run from anywhere in the repository. Needs Node.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
WEB="$ROOT/open-meridian/web"
OUT="$ROOT/open-meridian/plugin/web"

(cd "$WEB" && npm ci --ignore-scripts --no-audit --no-fund \
  && node node_modules/typescript/bin/tsc -p . \
  && node build.mjs)
node "$ROOT/open-meridian/ci/notices.mjs" "$WEB" "$OUT/NOTICES.txt"
# Only dockview-core's own error text names dockview-enterprise; no file of it
# is installed or bundled.
if [ -e "$WEB/node_modules/dockview-enterprise" ] || grep -n 'dockview-enterprise' "$WEB/bundled.json"; then
  echo "frontend: dockview-enterprise is installed or bundled" >&2
  exit 1
fi
echo "frontend: built into open-meridian/plugin/web ($(find "$OUT" -type f | wc -l | tr -d ' ') files)"
