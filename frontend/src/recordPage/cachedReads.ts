// `page.cached` for one visit: a kept value at once, and one fetch per key per visit.
import { keeperFor, keptValue } from "./keptValues";
import type { LateRefresh } from "./paintGate";

interface CachedRead {
  source: string;
  key: string;
  fetch: () => unknown;
  value: unknown;
  /** Set when the visit's one fetch starts. */
  landed?: Promise<void>;
}

export class CachedReads {
  private reads = new Map<string, CachedRead>();

  constructor(
    private readonly doctype: string,
    private readonly docname: string,
  ) {}

  /** The value this visit fetched, else the one an earlier visit kept; undefined before either. */
  read(source: string, key: string, fetch: () => unknown) {
    const id = storeKey(source, key);
    let read = this.reads.get(id);
    if (!read) {
      const kept = keptValue(this.doctype, this.docname, id);
      read = { source, key, fetch, value: kept?.value };
      this.reads.set(id, read);
    }
    read.fetch = fetch;
    return read.value;
  }

  /** Starts every read this visit has not fetched; answers, per source, when its fetches land. */
  fetchUnfetched(): LateRefresh[] {
    const started = new Map<string, Promise<void>[]>();
    for (const read of this.reads.values()) {
      if (read.landed) continue;
      read.landed = this.fetch(read);
      started.set(read.source, [...(started.get(read.source) ?? []), read.landed]);
    }
    return [...started].map(([source, landed]) => ({
      source,
      settled: Promise.all(landed).then(() => {}),
    }));
  }

  /** A failed fetch keeps the value the page already has. */
  private fetch(read: CachedRead): Promise<void> {
    const keep = keeperFor(this.doctype, this.docname);
    return new Promise((resolve) => resolve(read.fetch())).then(
      (value) => {
        read.value = value;
        keep(storeKey(read.source, read.key), value);
      },
      (error) => {
        console.warn(
          `[record-page] ${read.source} page.cached("${read.key}") on ${this.doctype} failed; the page keeps its last value.`,
          error,
        );
      },
    );
  }
}

function storeKey(source: string, key: string) {
  return `${source}\u0000${key}`;
}
