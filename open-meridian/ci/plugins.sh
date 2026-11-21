#!/bin/bash
# The run's plugins, made the way a person makes them with the released CLI:
# `meridian connect` (the person allows it in a browser: connect.py), then
# `upload` (built here with docker, into the deployment's own registry) and
# `launch` of each:
#   - plugin-ecb at a pinned commit, holding `data`, as instance `ecb`: the
#     ECB's reference rates, public and keyless. A data plugin resolves each
#     currency it records, which is what puts the euro's and the dollar's
#     cash instruments in the deployment's master: this plugin holds
#     `reporting`, whose lookups read the master and never add to it;
#   - this fork's plugin, holding `reporting`, as instance `desk`, its front
#     end built first (frontend.sh).
#
# The ECB publishes prices, not bars: the chart's bars are checked on the
# browser job's demo data (tests/fixtures), and on the deployment the chart
# is checked for saying so.
#
# Reads: RUN_DIR, KUBECONFIG, ECB_REPO, ECB_REV.
set -euo pipefail
: "${RUN_DIR:?}" "${KUBECONFIG:?}" "${ECB_REPO:?}" "${ECB_REV:?}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DASHBOARD=http://meridian.localhost

meridian connect "$DASHBOARD" >"$RUN_DIR/connect.log" 2>&1 &
connecting=$!
python3 "$HERE/connect.py" "$RUN_DIR/connect.log" "$RUN_DIR/person.json" "$DASHBOARD"
wait "$connecting" || { echo "plugins: meridian connect failed" >&2; sed -E 's/(code|state|code_challenge)=[^&[:space:]]*/\1=…/g' "$RUN_DIR/connect.log" >&2; exit 1; }

git init -q "$RUN_DIR/plugin-ecb"
git -C "$RUN_DIR/plugin-ecb" fetch -q --depth 1 "$ECB_REPO" "$ECB_REV"
git -C "$RUN_DIR/plugin-ecb" checkout -q FETCH_HEAD
meridian plugin upload --dir "$RUN_DIR/plugin-ecb"
meridian plugin launch ecb "$(sed -n 's/^version = "\(.*\)"/\1/p' "$RUN_DIR/plugin-ecb/pyproject.toml")" --instance ecb --yes

meridian plugin upload --dir "$HERE/../plugin"
meridian plugin launch desk "$(sed -n 's/^version = "\(.*\)"/\1/p' "$HERE/../plugin/pyproject.toml")" --instance desk --yes
for instance in ecb desk; do
  echo "plugins: waiting for ${instance}, at most 600s"
  kubectl -n meridian wait --for=condition=Available --timeout=600s "deployment/meridian-meridian-runtime-plugin-${instance}"
done
meridian plugin list
