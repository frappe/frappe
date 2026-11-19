// The default `page.cached`: one fetch per key while the route stays on one path; nothing is kept across visits.
import type { Router } from "vue-router";
import type { LateRefresh } from "./paintGate";

interface CachedRead {
  source: string;
  key: string;
  fetch: () => unknown;
  value: unknown;
  /** Set when the read's one fetch starts. */
  landed?: Promise<void>;
}

export class RouteCachedReads {
  private reads = new Map<string, CachedRead>();
  private path: string | null = null;

  constructor(
    private readonly router: Router,
    private readonly label: string,
  ) {}

  /** The value fetched on this path, or undefined before it lands. */
  read(source: string, key: string, fetch: () => unknown) {
    this.followRoute();
    const id = `${source}\u0000${key}`;
    let read = this.reads.get(id);
    if (!read) {
      read = { source, key, fetch, value: undefined };
      this.reads.set(id, read);
    }
    read.fetch = fetch;
    return read.value;
  }

  /** Starts every read not yet fetched; answers, per source, when its fetches land. */
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

  clear() {
    this.reads.clear();
    this.path = null;
  }

  private followRoute() {
    const path = this.router.currentRoute.value.path;
    if (path === this.path) return;
    this.reads.clear();
    this.path = path;
  }

  /** A failed fetch keeps the value the page already has. */
  private fetch(read: CachedRead): Promise<void> {
    const reads = this.reads;
    return new Promise((resolve) => resolve(read.fetch())).then(
      (value) => {
        // A read dropped by a route change meanwhile stays dropped.
        if (reads.get(`${read.source}\u0000${read.key}`) === read) read.value = value;
      },
      (error) => {
        console.warn(
          `${this.label} ${read.source} page.cached("${read.key}") failed; the page keeps its last value.`,
          error,
        );
      },
    );
  }
}
