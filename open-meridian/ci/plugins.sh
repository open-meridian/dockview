#!/bin/bash
# The run's plugins, made the way a person makes them with the released CLI:
# `meridian connect` (the person allows it in a browser: connect.py), then
# `upload` (built here with docker, into the deployment's own registry) and
# `launch` of each:
#   - plugin-truefx at a pinned commit, holding `data`, as instance `truefx`:
#     only when the run has a TrueFX username (the repository secret
#     TRUEFX_USERNAME). Without one it is skipped, saying so, and the price
#     and bar checks run on the browser job's demo data alone;
#   - this fork's plugin, holding `reporting`, as instance `desk`, its front
#     end built first (frontend.sh).
#
# Reads: RUN_DIR, KUBECONFIG, TRUEFX_REPO, TRUEFX_REV; TRUEFX_USERNAME if set
# (never printed: e2e.py enters it at the plugin's Settings form).
set -euo pipefail
: "${RUN_DIR:?}" "${KUBECONFIG:?}" "${TRUEFX_REPO:?}" "${TRUEFX_REV:?}"
HERE="$(cd "$(dirname "$0")" && pwd)"
DASHBOARD=http://meridian.localhost
instances=(desk)

meridian connect "$DASHBOARD" >"$RUN_DIR/connect.log" 2>&1 &
connecting=$!
python3 "$HERE/connect.py" "$RUN_DIR/connect.log" "$RUN_DIR/person.json" "$DASHBOARD"
wait "$connecting" || { echo "plugins: meridian connect failed" >&2; sed -E 's/(code|state|code_challenge)=[^&[:space:]]*/\1=…/g' "$RUN_DIR/connect.log" >&2; exit 1; }

if [ -n "${TRUEFX_USERNAME:-}" ]; then
  git init -q "$RUN_DIR/plugin-truefx"
  git -C "$RUN_DIR/plugin-truefx" fetch -q --depth 1 "$TRUEFX_REPO" "$TRUEFX_REV"
  git -C "$RUN_DIR/plugin-truefx" checkout -q FETCH_HEAD
  meridian plugin upload --dir "$RUN_DIR/plugin-truefx"
  meridian plugin launch truefx "$(sed -n 's/^version = "\(.*\)"/\1/p' "$RUN_DIR/plugin-truefx/pyproject.toml")" --instance truefx --yes
  instances+=(truefx)
  echo "with-truefx" >"$RUN_DIR/data"
else
  echo "::notice title=plugin-truefx skipped::No TRUEFX_USERNAME secret is set, so plugin-truefx is not installed. The watchlist's price and the chart's bars are checked on the browser job's demo data (tests/fixtures), not on the deployment."
  echo "plugins: plugin-truefx skipped: no TrueFX username"
  echo "demo-data-only" >"$RUN_DIR/data"
fi

meridian plugin upload --dir "$HERE/../plugin"
meridian plugin launch desk "$(sed -n 's/^version = "\(.*\)"/\1/p' "$HERE/../plugin/pyproject.toml")" --instance desk --yes
for instance in "${instances[@]}"; do
  echo "plugins: waiting for ${instance}, at most 600s"
  kubectl -n meridian wait --for=condition=Available --timeout=600s "deployment/meridian-meridian-runtime-plugin-${instance}"
done
meridian plugin list
