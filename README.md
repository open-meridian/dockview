> **This is Open Meridian's fork of [Dockview](https://github.com/dockview/dockview)**, showing Dockview working with
> [Open Meridian](https://open-meridian.dev). Our changes are on this branch (`open-meridian`); the `master`
> branch tracks upstream unchanged.
>
> Dockview's panel layouts hosting Open Meridian's order and execution views. This fork uses only Dockview's
> MIT-licensed packages; it doesn't modify or ship `dockview-enterprise`.
>
> ### Run it against your deployment
>
> The desk is a read-only plugin under [`open-meridian/`](open-meridian/): a blotter of orders, placements and fills,
> positions, a watchlist, a price chart ([OpenAlgo Charts](https://github.com/marketcalls/openalgo-charts)) and an
> instrument picker, in panels you dock, tab and float. It reads through its sidecar and shows each person only the
> accounts they may read on it. It places no order.
>
> You need Docker and the `meridian` CLI connected to a deployment where you are a deployment admin
> (`meridian connect <your dashboard>`).
>
> 1. Build the desk's front end: `open-meridian/ci/frontend.sh`.
> 2. Upload and launch the plugin:
>    `meridian plugin upload --dir open-meridian/plugin`, then
>    `meridian plugin launch desk 0.1.1 --instance desk`.
> 3. For prices and bars, launch a data plugin that records them, such as
>    [plugin-truefx](https://github.com/open-meridian/plugin-truefx). On **Data sources**, license its datasets and
>    entitle `desk` to them.
> 4. On **Access**, grant people View or Open on `desk`, on the accounts whose orders and positions they may see.
> 5. Open **desk** from the dashboard.
>
> Without a data plugin entitled, the watchlist and the chart say so instead of showing empty panels. The CI job in
> `.github/workflows/open-meridian.yml` runs these steps on a local development deployment, with plugin-truefx's
> sample data giving the chart its bars.
>
> This fork isn't listed in Open Meridian's plugin registry. What we add is under Dockview's MIT Licence; OpenAlgo
> Charts is under the Apache License 2.0, and its notices ship with the plugin. Where each part comes from is in
> [`open-meridian/PROVENANCE.md`](open-meridian/PROVENANCE.md).
>
> Dockview is licensed under MIT; this fork keeps that licence and its notices. It is not affiliated with or
> endorsed by Dockview's authors, or by OpenAlgo's.

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="static/img/dockview-lockup-dark.svg">
  <img src="static/img/dockview-lockup-light.svg" alt="Dockview" width="480">
</picture>

<h1>docking engine for the web</h1>

<p>Zero dependency layout manager supporting tabs, groups, grids and splitviews. Supports React, Vue, Angular and JavaScript</p>

[![npm version](https://img.shields.io/npm/v/dockview)](https://www.npmjs.com/package/dockview)
[![npm downloads](https://img.shields.io/npm/dm/dockview)](https://www.npmjs.com/package/dockview-core)
[![CI](https://img.shields.io/github/actions/workflow/status/dockview/dockview/main.yml?branch=master&label=CI)](https://github.com/dockview/dockview/actions?query=workflow%3ACI)
[![Coverage](https://img.shields.io/sonar/coverage/dockview_dockview?server=https%3A%2F%2Fsonarcloud.io)](https://sonarcloud.io/summary/overall?id=dockview_dockview)
[![Quality gate](https://img.shields.io/sonar/quality_gate/dockview_dockview?server=https%3A%2F%2Fsonarcloud.io)](https://sonarcloud.io/summary/overall?id=dockview_dockview)
[![Bundle size](https://img.shields.io/bundlephobia/minzip/dockview?label=size)](https://bundlephobia.com/result?p=dockview)

</div>

---

![A Dockview layout showing docked, tabbed and split panels in a trading workbench](static/img/demo-hero.webp)

Please see the website: https://dockview.dev

## Features

- Serialization / deserialization with full layout management
- Support for split-views, grid-views and 'dockable' views
- Themeable and customizable
- Tab and Group docking / Drag n' Drop
- Touch & mobile support
- Popout Windows
- Floating Groups
- Extensive API
- Supports Shadow DOMs
- High test coverage
- Documentation website with live examples
- Transparent builds and Code Analysis
- Security in mind - verified publishing and builds through GitHub Actions

## Packages

| Package                                                                    | Description                                                              | Version                                                                                                               |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| [`dockview`](https://www.npmjs.com/package/dockview)                       | JavaScript, zero dependencies, full feature set out of the box           | [![npm version](https://img.shields.io/npm/v/dockview)](https://www.npmjs.com/package/dockview)                       |
| [`dockview-react`](https://www.npmjs.com/package/dockview-react)           | React bindings (peer: `react` 16.8–19)                                   | [![npm version](https://img.shields.io/npm/v/dockview-react)](https://www.npmjs.com/package/dockview-react)           |
| [`dockview-vue`](https://www.npmjs.com/package/dockview-vue)               | Vue 3 bindings (peer: `vue` ≥3.4)                                        | [![npm version](https://img.shields.io/npm/v/dockview-vue)](https://www.npmjs.com/package/dockview-vue)               |
| [`dockview-angular`](https://www.npmjs.com/package/dockview-angular)       | Angular bindings (peer: `@angular/core` ≥21.0.6)                         | [![npm version](https://img.shields.io/npm/v/dockview-angular)](https://www.npmjs.com/package/dockview-angular)       |
| [`dockview-enterprise`](https://www.npmjs.com/package/dockview-enterprise) | Enterprise features, drop-in superset of `dockview` (commercial licence) | [![npm version](https://img.shields.io/npm/v/dockview-enterprise)](https://www.npmjs.com/package/dockview-enterprise) |

## Installation

```bash
npm install dockview          # JavaScript
npm install dockview-react    # React
npm install dockview-vue      # Vue
npm install dockview-angular  # Angular
```

## Quick Start (React)

```tsx
import { DockviewReact, themeDark } from 'dockview-react';
import 'dockview-react/dist/styles/dockview.css';

const components = {
  default: (props) => <div>Hello {props.params.title}</div>,
};

function App() {
  const onReady = (event) => {
    event.api.addPanel({
      id: 'panel_1',
      component: 'default',
      params: { title: 'World' },
    });
  };

  return (
    // Dockview fills its container, so the container needs a height of its own.
    <div style={{ height: '100dvh' }}>
      <DockviewReact
        theme={themeDark}
        onReady={onReady}
        components={components}
      />
    </div>
  );
}
```

For Vue and Angular examples see the [documentation](https://dockview.dev).

## Development

This project is a monorepo using [Yarn v1](https://classic.yarnpkg.com) workspaces.

```bash
yarn install    # Install dependencies
yarn build      # Build all packages
yarn test       # Run tests
yarn lint       # Lint all packages
yarn format     # Format all packages
```

## Contributing

Contributions are welcome! Please open an [issue](https://github.com/dockview/dockview/issues) or submit a pull request.

## Licence

This repository contains packages under more than one licence. Everything is MIT
except `dockview-enterprise`, which is proprietary and governed by a commercial
licence agreement.

See [LICENCE.md](./LICENCE.md) for the breakdown. Each published package ships
its own `LICENCE.md`, which is the authoritative licence for that package.

---

Want to verify our builds? Go [here](https://www.npmjs.com/package/dockview-react#Provenance).
