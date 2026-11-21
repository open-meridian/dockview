// The wrapper's read routes, on the plugin's own origin. Every one is a GET;
// the desk sends no change. A read the deployment declined answers
// `{refused: "..."}`, which each panel shows instead of empty data.

export type Refusable<T> = T & { refused?: string; error?: string };

export async function read<T>(route: string, query: Record<string, string> = {}): Promise<Refusable<T>> {
  const params = new URLSearchParams(query).toString();
  const answer = await fetch(`/api/${route}${params ? `?${params}` : ''}`, {
    credentials: 'same-origin',
    headers: { accept: 'application/json' },
  });
  if (!answer.ok && answer.status !== 400) {
    return { error: `the desk's ${route} answered ${answer.status}` } as Refusable<T>;
  }
  return (await answer.json()) as Refusable<T>;
}

export interface Pair {
  label: string;
  base: string;
  quote: string;
  description: string;
  identifiers: string[];
}

export interface Row {
  kind: 'order' | 'placement' | 'fill';
  id: string;
  order_id: string;
  account: string;
  instrument: string;
  side: string;
  quantity: string;
  price: string;
  state: string;
  at: string;
  at_ns: number;
  last_change: string;
  sequence: number;
}

export interface Holding {
  account: string;
  instrument: string;
  side: string;
  quantity: string;
  settled: string;
  last_change: string;
}

export interface Latest {
  price?: string;
  kind?: string;
  at?: string;
  recorded_at?: string;
  dataset?: string;
}

export interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  dataset: string;
}

export const pairQuery = (pair: Pair): Record<string, string> => ({ base: pair.base, quote: pair.quote });
