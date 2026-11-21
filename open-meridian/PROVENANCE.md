# Provenance

This branch, `open-meridian`, adds an Open Meridian plugin to Dockview. Upstream's default branch is untouched, and
so is Dockview's library (`packages/`): the desk uses Dockview's MIT packages as published on npm, pinned. What we
add is under Dockview's MIT Licence, as `LICENCE.md` says of the rest of this repository. This file lists where each
part comes from, and every upstream file we change.

## What we add

| Path | What | From |
|---|---|---|
| `open-meridian/plugin/` | The plugin: the wrapper that serves the desk and its read routes, reading the book and the lake through the plugin's sidecar and cutting rows to each person's accounts | Written here, on the Open Meridian SDK (`open-meridian==0.37.1`, Apache-2.0) |
| `open-meridian/plugin/tests/fixtures/` | Demo data for the tests: a `ListOrdersResult`, a `ListPositionsResult` and a `ListBarsResult` | Written here; made up, not recorded from any market or book |
| `open-meridian/web/` | The desk's front end: Dockview's panels, the read-only panels, and our feed adapter for the chart | Written here, on `dockview-core` and `dockview-react` 8.9.1 (MIT), `openalgo-charts` 2.7.3 (Apache-2.0) and React 19.2.0 (MIT) |
| `open-meridian/ci/first_run.py`, `deployment.sh`, `platform.sh`, `connect.py`, `plugins.sh`, `notices.mjs` | First run, the k3d deployment from the released CLI and chart, the platform-master stand-in, `meridian connect`, the uploads, and the notices | open-meridian/finos-workspace@bb6798eac04b1fa649d958c89ce28f11100d461a `open-meridian/ci/` (written by Open Meridian), adapted: a third person, plugin-truefx when its username is set, the desk's own build |
| `open-meridian/ci/*` (the rest), `.github/workflows/open-meridian.yml` | The fork's checks and CI job | Written here |

## Libraries the desk ships

- **Dockview** (`dockview-core`, `dockview`, `dockview-react`, 8.9.1): MIT. Only these packages are used.
  `dockview-enterprise`, in upstream's tree under a proprietary licence, is never a dependency, never imported and
  never in the image: `ci/checks.sh` and `ci/frontend.sh` fail if it is.
- **OpenAlgo Charts** (`openalgo-charts` 2.7.3, by marketcalls): Apache-2.0. Its `LICENSE` (the Apache License 2.0)
  and `NOTICE` were read from the published package on 2026-11-20 before it entered this branch; both are shipped in
  the image's `NOTICES.txt`. Only its base engine is used: not its data feeds, CDN build, symbol search, widget,
  workspace or trade tiers. Its corner branding and watermark are off.
- **React** and **React DOM** 19.2.0: MIT.

Every package the front end's build ships is listed, with its licence text, in `NOTICES.txt` in the image; the build
fails on a package under the AGPL, the GPL or the SSPL.

## Clean room

The default layout (an instrument picker and watchlist beside a chart, with the blotter and positions as tabs below)
follows the arrangement commercial order and execution management systems show in public material. It was written
from that public description alone: no product's source, private documentation or assets were read or copied, and
no reference project's code is used.

## Upstream files we change

- `README.md`: the fork's opening section.
