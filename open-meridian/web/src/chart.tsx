// The price chart: OpenAlgo Charts' base engine, fed by our own adapter from
// the wrapper's bar routes. Not used of it: its data feeds, its CDN build,
// its symbol search, its widget tier (with its browser-saved drawings and
// layouts) and its trade tier (with its order hooks). Its corner branding and
// watermark are off; it is themed from the kit's tokens. It follows its
// container's size itself.
import { useEffect, useRef, useState } from 'react';
import { createChart, darkTheme, lightTheme } from 'openalgo-charts';
import type { Chart as Engine, ChartTheme } from 'openalgo-charts';
import { read, pairQuery } from './api';
import type { Bar, Pair } from './api';

/** A kit token's value on the page, or the fallback. */
function token(name: string, fallback: string, at: Element = document.documentElement): string {
  const value = getComputedStyle(at).getPropertyValue(name).trim();
  return value || fallback;
}

/** The chart's colours from the kit's tokens, over the engine's own theme
 * for the person's light or dark mode. */
export function kitTheme(at: Element): ChartTheme {
  const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  const base = dark ? darkTheme : lightTheme;
  const up = token('--buy', base.upColor, at);
  const down = token('--sell', base.downColor, at);
  return {
    ...base,
    background: token('--card', base.background, at),
    grid: token('--line-soft', base.grid, at),
    axisText: token('--ink-soft', base.axisText, at),
    axisLine: token('--line', base.axisLine, at),
    paneSeparator: token('--line', base.paneSeparator, at),
    crosshair: token('--ink-faint', base.crosshair, at),
    upColor: up,
    downColor: down,
    wickUpColor: up,
    wickDownColor: down,
    lineColor: token('--accent', base.lineColor, at),
    lastPriceUp: up,
    lastPriceDown: down,
    buy: up,
    sell: down,
  };
}

/** Our feed adapter: the wrapper's bars, as the engine takes them. */
export async function barsFor(pair: Pair, interval: string): Promise<{ bars?: Bar[]; refused?: string }> {
  const answer = await read<{ bars: Bar[] }>('bars', { ...pairQuery(pair), interval });
  if (answer.refused || answer.error) return { refused: answer.refused ?? answer.error };
  return { bars: answer.bars };
}

export function ChartView({ pair }: { pair: Pair }) {
  const holder = useRef<HTMLDivElement>(null);
  const engine = useRef<Engine | null>(null);
  const [intervals, setIntervals] = useState<string[] | null>(null);
  const [interval, setInterval] = useState('');
  const [problem, setProblem] = useState('');
  const [last, setLast] = useState<Bar | null>(null);

  useEffect(() => {
    let gone = false;
    let again = 0;
    setIntervals(null);
    setProblem('');
    // Asked again every 30 seconds while no length is held, as the bars are
    // read again: a lake that has just asked a data plugin for them holds
    // them once it answers.
    const probe = () =>
      void read<{ intervals: string[] }>('intervals', pairQuery(pair)).then((answer) => {
        if (gone) return;
        if (answer.refused || answer.error) {
          setProblem(answer.refused ?? answer.error ?? '');
          setIntervals([]);
        } else {
          setProblem('');
          setIntervals(answer.intervals);
          setInterval((held) => (answer.intervals.includes(held) ? held : (answer.intervals.at(-1) ?? '')));
          if (answer.intervals.length) return;
        }
        again = window.setTimeout(probe, 30_000);
      });
    probe();
    return () => {
      gone = true;
      window.clearTimeout(again);
    };
  }, [pair.label]);

  useEffect(() => {
    const el = holder.current;
    if (!el || !interval) return;
    const chart = createChart(el, {
      theme: kitTheme(el),
      branding: false,
      watermark: false,
      timezone: 'UTC',
    });
    engine.current = chart;
    const series = chart.addSeries('candlestick');
    let gone = false;
    const load = async () => {
      const answer = await barsFor(pair, interval);
      if (gone) return;
      if (answer.refused) {
        setProblem(answer.refused);
        return;
      }
      setProblem('');
      const bars = answer.bars ?? [];
      series.setData(bars.map(({ time, open, high, low, close }) => ({ time, open, high, low, close })));
      setLast(bars.at(-1) ?? null);
      chart.fitContent();
    };
    void load();
    const timer = window.setInterval(load, 30_000);
    return () => {
      gone = true;
      window.clearInterval(timer);
      chart.destroy();
      engine.current = null;
    };
  }, [pair.label, interval]);

  const lastTime = last ? new Date(last.time * 1000).toISOString().replace('.000Z', 'Z') : '';
  return (
    <div className="chart" data-chart={pair.label}>
      <header className="panel-head">
        <span>{pair.label}</span>
        <span className="intervals">
          {(intervals ?? []).map((each) => (
            <button
              key={each}
              type="button"
              className={each === interval ? 'on' : ''}
              aria-pressed={each === interval}
              onClick={() => setInterval(each)}
            >
              {each}
            </button>
          ))}
        </span>
        <span className="muted" data-last-bar={lastTime}>
          {last ? `Last bar ${lastTime}, close ${last.close} (${last.dataset})` : ''}
        </span>
      </header>
      {problem ? (
        <p className="refused" role="status">
          <strong>Refused:</strong> {problem}
        </p>
      ) : intervals !== null && intervals.length === 0 ? (
        <p className="empty">The lake holds no bars of {pair.label} at any length.</p>
      ) : null}
      <div className="chart-canvas" ref={holder} hidden={!!problem || !interval} />
    </div>
  );
}
