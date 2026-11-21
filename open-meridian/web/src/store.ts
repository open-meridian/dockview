// What the panels share inside one desk, for the page's life only: the
// instrument picked and the watchlist. Nothing is saved anywhere.
import { useSyncExternalStore } from 'react';
import type { Pair } from './api';

interface State {
  picked: Pair | null;
  watched: Pair[];
}

let state: State = { picked: null, watched: [] };
const listeners = new Set<() => void>();

export function pick(pair: Pair): void {
  const watched = state.watched.some((p) => p.label === pair.label) ? state.watched : [...state.watched, pair];
  state = { picked: pair, watched };
  listeners.forEach((l) => l());
}

export function unwatch(label: string): void {
  state = { ...state, watched: state.watched.filter((p) => p.label !== label) };
  listeners.forEach((l) => l());
}

export function useDesk(): State {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => state,
  );
}
