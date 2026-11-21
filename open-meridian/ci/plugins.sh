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
#   - plugin-truefx at a pinned commit, holding `data`, as instance `truefx`:
#     public and keyless too. The ECB publishes prices, not bars; TrueFX's
#     daily dataset holds each pair's day as a bar. On this development
#     deployment e2e.py switches its sample data on, so its bars are the
#     history files it carries, never TrueFX called;
#   - this fork's plugin, holding `reporting`, as instance `desk`, its front
#     end built first (frontend.sh).
#
# Reads: RUN_DIR, KUBECONFIG, ECB_REPO, ECB_REV, TRUEFX_REPO, TRUEFX_REV.
set -euo pipefail
: "${RUN_DIR:?}" "${KUBECONFIG:?}" "${ECB_REPO:?}" "${ECB_REV:?}" "${TRUEFX_REPO:?}" "${TRUEFX_REV:?}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DASHBOARD=http://meridian.localhost

meridian connect "$DASHBOARD" >"$RUN_DIR/connect.log" 2>&1 &
connecting=$!
python3 "$HERE/connect.py" "$RUN_DIR/connect.log" "$RUN_DIR/person.json" "$DASHBOARD"
wait "$connecting" || { echo "plugins: meridian connect failed" >&2; sed -E 's/(code|state|code_challenge)=[^&[:space:]]*/\1=…/g' "$RUN_DIR/connect.log" >&2; exit 1; }

# A data plugin at its pinned commit, uploaded and launched: name, instance,
# repository, commit.
data_plugin() {
  local name="$1" instance="$2" repo="$3" rev="$4" dir="$RUN_DIR/plugin-$1"
  git init -q "$dir"
  git -C "$dir" fetch -q --depth 1 "$repo" "$rev"
  git -C "$dir" checkout -q FETCH_HEAD
  meridian plugin upload --dir "$dir"
  meridian plugin launch "$name" "$(sed -n 's/^version = "\(.*\)"/\1/p' "$dir/pyproject.toml")" --instance "$instance" --yes
}
data_plugin ecb ecb "$ECB_REPO" "$ECB_REV"
data_plugin truefx truefx "$TRUEFX_REPO" "$TRUEFX_REV"

meridian plugin upload --dir "$HERE/../plugin"
meridian plugin launch desk "$(sed -n 's/^version = "\(.*\)"/\1/p' "$HERE/../plugin/pyproject.toml")" --instance desk --yes
for instance in ecb truefx desk; do
  echo "plugins: waiting for ${instance}, at most 600s"
  kubectl -n meridian wait --for=condition=Available --timeout=600s "deployment/meridian-meridian-runtime-plugin-${instance}"
done
meridian plugin list
