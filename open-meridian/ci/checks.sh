#!/bin/bash
# What this fork adds, held to its rules. Run from the repository's root.
#
# 1. Upstream: every upstream file this branch changes is listed in
#    open-meridian/PROVENANCE.md, and Dockview's licence is unchanged.
#    Dockview's own library (packages/) is never changed.
# 2. Names: nothing we add names a persona, a private sample or an internal name.
# 3. Licences: nothing we add carries an AGPL or GPL notice; the provenance
#    file is there; `dockview-enterprise` (proprietary, in upstream's tree) is
#    neither a dependency nor imported by anything we add.
# 4. No route out: the wrapper's code holds no HTTP client and no socket, and
#    the desk's code names no address, socket or event stream of another origin.
# 5. No order path: nothing we add imports OpenAlgo Charts' trade or widget
#    tier, hands it an order hook, or calls an order act.
# 6. Colour: the desk's own UI draws with the kit's tokens (CSS custom
#    properties): no raw colour in its styles, markup or scripts, whether a
#    hex, a colour function (rgb(), hsl() and the like) or a colour's name.
set -euo pipefail
failed=0
fail() { echo "checks: $*" >&2; failed=1; }
base="${BASE_REF:-origin/open-meridian}"
ours=(open-meridian .github/workflows/open-meridian.yml)
skip=(--exclude=checks.sh --exclude-dir=node_modules --exclude-dir=web --exclude-dir=.venv --exclude-dir=fixtures --exclude=package-lock.json)
src=(open-meridian/web/src open-meridian/web/index.html open-meridian/web/popout.html open-meridian/web/build.mjs)

# 1. Upstream.
while IFS= read -r changed; do
  case "$changed" in open-meridian/*|.github/workflows/open-meridian.yml|README.md) continue ;; esac
  grep -qF "\`$changed\`" open-meridian/PROVENANCE.md || fail "upstream's $changed changes and PROVENANCE.md does not list it"
done < <(git diff --name-only "$base"...HEAD)
git diff --quiet "$base"...HEAD -- LICENCE.md packages || fail "Dockview's licence or its library (packages/) changed"

# 2. Names.
if grep -RIniE 'persona|trader persona|researcher|plugin-sample|sample-(fx|multi-asset|options|pricing|reporting|operations)|discretionary pm|systematic pm' \
     "${ours[@]}" "${skip[@]}"; then
  fail "a persona, a private sample or an internal name appears in what we add"
fi

# 3. Licences.
if grep -RIlE 'GNU (Affero )?General Public License|AGPL-3|SPDX-License-Identifier: *(A?GPL)' "${ours[@]}" "${skip[@]}"; then
  fail "an AGPL or GPL notice in what we add"
fi
grep -q '^## MIT Licence' LICENCE.md || fail "Dockview's MIT licence, which covers what we add, is not at LICENCE.md"
[ -f open-meridian/PROVENANCE.md ] || fail "open-meridian/PROVENANCE.md is missing"
if grep -RnE 'dockview-enterprise' open-meridian/web/package.json open-meridian/web/package-lock.json "${src[@]}" open-meridian/plugin/src; then
  fail "dockview-enterprise is named by the desk: only Dockview's MIT packages are used"
fi

# 4. No route out.
if grep -RnE '^\s*(import|from) (urllib\.request|http\.client|socket|requests|httpx|aiohttp)\b' open-meridian/plugin/src; then
  fail "the wrapper imports an HTTP client or a socket: it reaches only its sidecar"
fi
if grep -RnE 'https?://|wss?://|new WebSocket|EventSource|navigator\.sendBeacon' "${src[@]}" | grep -v 'www.w3.org/2000/svg'; then
  fail "the desk names another origin, a socket or an event stream: it reads only its own origin"
fi

# 5. No order path.
if grep -RnE "openalgo-charts/(trade|widget|workspace)|onOrder|OpenAlgo(Trade|Live|Ws)?(DataFeed|Feed)|addOrder|placeOrder" "${src[@]}"; then
  fail "the desk imports OpenAlgo Charts' trade, widget or workspace tier, its feeds, or an order hook"
fi
if grep -RnE "\b(create_order|amend_order|cancel_order|release_order|create_placement|amend_placement|cancel_placement)\b" open-meridian/plugin/src; then
  fail "the wrapper calls an order act"
fi
if grep -RnE "method: *['\"](POST|PUT|PATCH|DELETE)" "${src[@]}"; then
  fail "the desk sends a change: every route it calls is a read"
fi

# 6. Colour.
colours=(open-meridian/web/src open-meridian/web/index.html open-meridian/web/popout.html)
if grep -RnE '(^|[^&0-9A-Za-z_])#[0-9a-fA-F]{3,8}\b|\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(' "${colours[@]}"; then
  fail "the desk's own UI writes a raw colour: use the kit's tokens, var(--...)"
fi
if grep -RniE "[:'\"=(,[:space:]](white|black|red|green|blue|gray|grey|orange|yellow|purple|pink|silver|navy|maroon|teal|olive|lime|aqua|fuchsia)\s*[;'\",)!]" "${colours[@]}"; then
  fail "the desk's own UI names a colour: use the kit's tokens, var(--...)"
fi

[ "$failed" -eq 0 ] && echo "checks: upstream untouched, names, licences, no dockview-enterprise, no route out, no order path and no raw colour hold"
exit "$failed"
