// The desk: Dockview's docking layout (its MIT packages, as published) holding
// the read-only panels. Panels dock, tab, float and pop out within the page;
// the layout lasts while the page is open and is kept nowhere. "Reset layout"
// puts the default back.
import { StrictMode, useCallback, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { DockviewReact, themeLight } from 'dockview-react';
import type { DockviewApi, DockviewReadyEvent, IDockviewPanelProps } from 'dockview-react';
import 'dockview-react/dist/styles/dockview.css';
import './desk.css';
import { Blotter, Chart, Picker, Positions, Watchlist } from './panels';

const components: Record<string, React.FunctionComponent<IDockviewPanelProps>> = {
  blotter: () => <Blotter />,
  positions: () => <Positions />,
  watchlist: () => <Watchlist />,
  chart: () => <Chart />,
  picker: () => <Picker />,
};

const TITLES: Record<string, string> = {
  picker: 'Instrument',
  watchlist: 'Watchlist',
  chart: 'Chart',
  blotter: 'Blotter',
  positions: 'Positions',
};

/** Below this width the default layout is one group of tabs. */
const NARROW = 768;

/** The default layout, shipped in the image: on a wide page the picker and
 * watchlist on the left, the chart beside them, the blotter and positions as
 * tabs below; on a narrow one, every panel a tab of one group. */
export function defaultLayout(api: DockviewApi): void {
  api.clear();
  const add = (id: string, position?: Parameters<DockviewApi['addPanel']>[0]['position']) =>
    api.addPanel({ id, component: id, title: TITLES[id], position });
  if (window.innerWidth < NARROW) {
    add('chart');
    for (const id of ['watchlist', 'picker', 'blotter', 'positions']) add(id, { referencePanel: 'chart', direction: 'within' });
    api.getPanel('chart')?.api.setActive();
    return;
  }
  add('chart');
  add('picker', { referencePanel: 'chart', direction: 'left' });
  add('watchlist', { referencePanel: 'picker', direction: 'below' });
  add('blotter', { referencePanel: 'chart', direction: 'below' });
  add('positions', { referencePanel: 'blotter', direction: 'within' });
  api.getPanel('blotter')?.api.setActive();
  api.getPanel('picker')?.api.setSize({ width: 300 });
}

function Desk() {
  const api = useRef<DockviewApi | null>(null);

  const onReady = useCallback((event: DockviewReadyEvent) => {
    api.current = event.api;
    defaultLayout(event.api);
  }, []);

  const active = () => api.current?.activePanel;

  return (
    <div className="desk">
      <nav className="desk-bar" aria-label="Layout">
        <span className="desk-title">Desk</span>
        <span className="desk-note">Read-only: orders are not placed here.</span>
        <span className="desk-actions">
          <button
            type="button"
            data-action="float"
            onClick={() => {
              const panel = active();
              if (panel && api.current) api.current.addFloatingGroup(panel, { width: 420, height: 300 });
            }}
          >
            Float
          </button>
          <button
            type="button"
            data-action="popout"
            onClick={() => {
              const panel = active();
              if (panel && api.current) void api.current.addPopoutGroup(panel, { popoutUrl: '/popout.html' });
            }}
          >
            Pop out
          </button>
          <button type="button" data-action="reset" onClick={() => api.current && defaultLayout(api.current)}>
            Reset layout
          </button>
        </span>
      </nav>
      <DockviewReact
        className="desk-dock"
        theme={themeLight}
        components={components}
        onReady={onReady}
        floatingGroupBounds="boundedWithinViewport"
      />
    </div>
  );
}

createRoot(document.getElementById('desk')!).render(
  <StrictMode>
    <Desk />
  </StrictMode>,
);
