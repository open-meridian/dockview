#!/bin/bash
# The desk's front end, built for the plugin's image into
# open-meridian/plugin/web, inside a container (frontend.Dockerfile): the
# pinned packages installed, type-checked and bundled, the notices of every
# package it ships, refused if any is under a GPL-family licence or is
# dockview-enterprise, and the files bundled searched for dockview-enterprise.
#
# Run from anywhere in the repository. Needs Docker, nothing else: the Node
# that builds it is the image's, pinned by digest.
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
OUT="$ROOT/open-meridian/plugin/web"

# What a build before this one left is gone first, so web/ holds this build's
# files alone; a failed build leaves no web/, which the plugin's image refuses.
rm -rf "$OUT"
docker build -f "$ROOT/open-meridian/ci/frontend.Dockerfile" --output "type=local,dest=$OUT" "$ROOT"
# The exporter makes web/ itself readable by its owner alone; the plugin's
# image runs as another user, which reads every file of it.
chmod -R u+rwX,go+rX "$OUT"
test -s "$OUT/index.html" && test -s "$OUT/NOTICES.txt"
echo "frontend: built into open-meridian/plugin/web ($(find "$OUT" -type f | wc -l | tr -d ' ') files)"
