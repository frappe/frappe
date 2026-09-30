import { onRecordLeft, readCachedDocument } from "../../cache";
import { docKey } from "./pendingRows";
import type { TimelineStore } from "./timelineStore";

// idle stores kept for records the shared cache does not hold; past this, the least recently used goes
const UNCACHED_STORES = 20;

/** Stores by cache key, most recently used last; an idle one lives as long as its record's cache entry. */
export class StoreCache {
  private readonly stores = new Map<string, TimelineStore>();
  // open holds per key: a page's prefetch or staged read, or a reload's read
  private readonly held = new Map<string, number>();

  constructor() {
    onRecordLeft((doctype, name) => this.dropIdle(docKey(doctype, name)));
  }

  get(key: string): TimelineStore | undefined {
    const store = this.stores.get(key);
    if (!store) return undefined;
    this.stores.delete(key);
    this.stores.set(key, store);
    return store;
  }

  add(key: string, store: TimelineStore) {
    this.stores.set(key, store);
    this.trim();
  }

  hold(key: string) {
    this.held.set(key, (this.held.get(key) ?? 0) + 1);
  }

  /** Ends one hold; an end with no hold open ends nothing. */
  letGo(key: string) {
    const count = this.held.get(key) ?? 0;
    if (count > 1) this.held.set(key, count - 1);
    else this.held.delete(key);
    this.trim();
  }

  /** Keeps at most 20 idle stores whose record is not cached, dropping the least recently used. */
  trim() {
    const uncached = [...this.stores].filter(([, store]) => store.mounted === 0 && !isCached(store));
    for (const [key, store] of uncached.slice(0, -UNCACHED_STORES)) this.drop(key, store);
  }

  private dropIdle(doc: string) {
    for (const [key, store] of this.stores) {
      if (store.doc === doc && store.mounted === 0 && !this.held.has(key)) this.drop(key, store);
    }
  }

  private drop(key: string, store: TimelineStore) {
    this.stores.delete(key);
    this.held.delete(key);
    store.dispose();
  }
}

function isCached(store: TimelineStore): boolean {
  return readCachedDocument(store.doctype, store.docname)?.complete === true;
}
