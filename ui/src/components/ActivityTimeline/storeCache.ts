import { onRecordLeft, readCachedDocument } from "../../cache";
import { docKey } from "./pendingRows";
import type { TimelineStore } from "./timelineStore";

// idle stores kept for records the shared cache does not hold
const UNCACHED_STORES = 20;

/** Stores by cache key, most recently used last; the shared cache or a limit keeps idle ones. */
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

  /** The store's last component left: it counts as just used. */
  release(key: string) {
    this.get(key);
    this.trim();
  }

  /** Drops the least recently used idle stores the cache does not hold, past `UNCACHED_STORES`. */
  trim() {
    // a held store counts, so a hold never let go is bounded too
    const idle = [...this.stores].filter(([, store]) => !inUse(store) && !isCached(store));
    for (const [key, store] of idle.slice(0, -UNCACHED_STORES)) this.drop(key, store);
  }

  private dropIdle(doc: string) {
    for (const [key, store] of this.stores) {
      if (store.doc === doc && store.mounted === 0 && !this.held.has(key)) this.drop(key, store);
    }
    this.trim();
  }

  private drop(key: string, store: TimelineStore) {
    this.stores.delete(key);
    store.dispose();
  }
}

function inUse(store: TimelineStore): boolean {
  return store.mounted > 0 || store.awaitingPage;
}

function isCached(store: TimelineStore): boolean {
  return readCachedDocument(store.doctype, store.docname)?.complete === true;
}
