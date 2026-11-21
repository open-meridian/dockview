// The desk's panels, every one read-only: no control here places, amends,
// cancels or releases anything, and none calls a route that changes
// something (the wrapper serves none).
import { useEffect, useRef, useState } from 'react';
import { read, pairQuery } from './api';
import type { Holding, Latest, Pair, Row } from './api';
import { pick, unwatch, useDesk } from './store';
import { ChartView } from './chart';

/** Calls `fn` now and every `seconds` while the panel is shown. */
function usePoll(fn: () => Promise<void> | void, seconds: number, deps: unknown[]): void {
  useEffect(() => {
    let stopped = false;
    const run = async () => {
      if (!stopped) await fn();
    };
    void run();
    const timer = window.setInterval(run, seconds * 1000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

function Refusal({ text }: { text: string }) {
  return (
    <p className="refused" role="status">
      <strong>Refused:</strong> {text}
    </p>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="empty">{text}</p>;
}

const rowKey = (r: Row) => `${r.kind}:${r.id}`;

export function Blotter() {
  const [rows, setRows] = useState<Row[]>([]);
  const [accounts, setAccounts] = useState<string[] | null>(null);
  const [problem, setProblem] = useState('');
  const [checked, setChecked] = useState('');
  const since = useRef('');

  useEffect(() => {
    void read<{ accounts: string[] }>('me').then((me) => setAccounts(me.accounts ?? []));
  }, []);

  usePoll(
    async () => {
      const answer = await read<{ rows: Row[]; since: string; changed_only: boolean }>(
        'blotter',
        since.current ? { since: since.current } : {},
      );
      if (answer.refused || answer.error) {
        setProblem(answer.refused ?? answer.error ?? '');
        return;
      }
      setProblem('');
      since.current = answer.since;
      setRows((held) => {
        if (!answer.changed_only) return answer.rows;
        const merged = new Map(held.map((r) => [rowKey(r), r]));
        answer.rows.forEach((r) => merged.set(rowKey(r), r));
        return [...merged.values()].sort((a, b) => b.at_ns - a.at_ns || b.sequence - a.sequence);
      });
      setChecked(new Date().toISOString().slice(11, 19) + 'Z');
    },
    10,
    [],
  );

  return (
    <section className="panel" data-panel="blotter">
      <header className="panel-head">
        <span>Orders, placements and fills</span>
        <span className="muted" data-accounts={accounts?.join(',') ?? ''}>
          {accounts === null ? '' : accounts.length ? `Accounts: ${accounts.join(', ')}` : 'No account'}
          {checked && ` · read ${checked}`}
        </span>
      </header>
      {problem ? (
        <Refusal text={problem} />
      ) : rows.length === 0 ? (
        <Empty text="No order, placement or fill on the accounts you may read." />
      ) : (
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr>
                <th>Time</th>
                <th>Kind</th>
                <th>ID</th>
                <th>Account</th>
                <th>Instrument</th>
                <th>Side</th>
                <th className="num">Quantity</th>
                <th className="num">Price</th>
                <th>State</th>
                <th>Last change</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={rowKey(r)} data-kind={r.kind}>
                  <td>{r.at}</td>
                  <td>{r.kind}</td>
                  <td>{r.id}</td>
                  <td>{r.account}</td>
                  <td>{r.instrument}</td>
                  <td className={r.side.startsWith('buy') ? 'buy' : r.side ? 'sell' : ''}>{r.side}</td>
                  <td className="num">{r.quantity}</td>
                  <td className="num">{r.price}</td>
                  <td>{r.state}</td>
                  <td>{r.last_change}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function Positions() {
  const [rows, setRows] = useState<Holding[] | null>(null);
  const [problem, setProblem] = useState('');
  usePoll(
    async () => {
      const answer = await read<{ rows: Holding[] }>('positions');
      setProblem(answer.refused ?? answer.error ?? '');
      if (!answer.refused && !answer.error) setRows(answer.rows);
    },
    30,
    [],
  );
  return (
    <section className="panel" data-panel="positions">
      <header className="panel-head">
        <span>Positions</span>
      </header>
      {problem ? (
        <Refusal text={problem} />
      ) : rows === null ? null : rows.length === 0 ? (
        <Empty text="No position on the accounts you may read." />
      ) : (
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr>
                <th>Account</th>
                <th>Instrument</th>
                <th>Side</th>
                <th className="num">Trade-date quantity</th>
                <th className="num">Settled</th>
                <th>Last change</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((h) => (
                <tr key={`${h.account}:${h.instrument}`}>
                  <td>{h.account}</td>
                  <td>{h.instrument}</td>
                  <td>{h.side}</td>
                  <td className="num">{h.quantity}</td>
                  <td className="num">{h.settled}</td>
                  <td>{h.last_change}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Quote({ pair, active }: { pair: Pair; active: boolean }) {
  const [latest, setLatest] = useState<Latest | null>(null);
  const [problem, setProblem] = useState('');
  usePoll(
    async () => {
      const answer = await read<{ latest: Latest }>('price', pairQuery(pair));
      setProblem(answer.refused ?? answer.error ?? '');
      if (!answer.refused && !answer.error) setLatest(answer.latest);
    },
    15,
    [pair.label],
  );
  return (
    <tr data-pair={pair.label} className={active ? 'active' : ''}>
      <td>
        <button type="button" className="link" onClick={() => pick(pair)}>
          {pair.label}
        </button>
      </td>
      {problem ? (
        <td colSpan={3}>
          <Refusal text={problem} />
        </td>
      ) : latest && latest.price ? (
        <>
          <td className="num price">{latest.price}</td>
          <td className="time">{latest.at}</td>
          <td className="muted">{latest.dataset}</td>
        </>
      ) : (
        <td colSpan={3} className="muted">
          {latest ? 'The lake holds no price for it yet.' : ''}
        </td>
      )}
      <td>
        <button type="button" className="ghost" aria-label={`Stop watching ${pair.label}`} onClick={() => unwatch(pair.label)}>
          ×
        </button>
      </td>
    </tr>
  );
}

export function Watchlist() {
  const { watched, picked } = useDesk();
  return (
    <section className="panel" data-panel="watchlist">
      <header className="panel-head">
        <span>Watchlist</span>
        <span className="muted">Latest price, polled</span>
      </header>
      {watched.length === 0 ? (
        <Empty text="Pick an instrument to watch it." />
      ) : (
        <div className="table-wrap">
          <table className="grid">
            <thead>
              <tr>
                <th>Instrument</th>
                <th className="num">Price</th>
                <th>Time</th>
                <th>Dataset</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {watched.map((p) => (
                <Quote key={p.label} pair={p} active={picked?.label === p.label} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function Chart() {
  const { picked } = useDesk();
  return (
    <section className="panel" data-panel="chart">
      {picked ? <ChartView pair={picked} /> : <Empty text="Pick an instrument to chart it." />}
    </section>
  );
}

export function Picker() {
  const [asked, setAsked] = useState('');
  const [said, setSaid] = useState('');
  const { picked } = useDesk();

  const look = async (query: string) => {
    if (!query.trim()) return;
    setSaid('Looking it up…');
    const answer = await read<{ found: Pair | null }>('lookup', { q: query });
    if (answer.refused || answer.error) {
      setSaid(answer.refused ?? answer.error ?? '');
      return;
    }
    if (!answer.found) {
      setSaid(`The deployment's master holds nothing for ${query.trim()}.`);
      return;
    }
    setSaid('');
    pick(answer.found);
  };

  useEffect(() => {
    // The desk opens on a pair, so its panels show something at once.
    if (!picked) void look('EUR/USD');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="panel" data-panel="picker">
      <form
        className="picker"
        onSubmit={(e) => {
          e.preventDefault();
          void look(asked);
        }}
      >
        <label htmlFor="pick">Instrument</label>
        <input
          id="pick"
          name="pick"
          value={asked}
          placeholder="EUR/USD, a code, a FIGI, an ISIN, a ticker or an ID"
          onChange={(e) => setAsked(e.target.value)}
          autoComplete="off"
        />
        <button type="submit">Show</button>
      </form>
      {said && <p className="muted" role="status">{said}</p>}
      {picked && (
        <dl className="picked" data-picked={picked.label}>
          <dt>Showing</dt>
          <dd>{picked.label}</dd>
          <dt>Instrument</dt>
          <dd>{picked.quote ? `${picked.base} in ${picked.quote}` : picked.base}</dd>
          {picked.description && (
            <>
              <dt>Description</dt>
              <dd>{picked.description}</dd>
            </>
          )}
        </dl>
      )}
      <p className="muted small">Looked up by identifier in the deployment's master; the watchlist and the chart follow.</p>
    </section>
  );
}
