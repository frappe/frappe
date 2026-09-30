import { onRecordLeft, readCachedDocument } from "../../cache";
import { docKey } from "./pendingRows";
import type { TimelineStore } from "./timelineStore";

/** Stores by cache key; an idle one lives as long as its record's complete entry in the shared cache. */
export class StoreCache {
  private readonly stores = new Map<string, TimelineStore>();
  // keys a page's first paint reads from, whatever the cache holds
  private readonly held = new Set<string>();

  constructor() {
    onRecordLeft((doctype, name) => this.dropIdle(docKey(doctype, name)));
  }

  get(key: string): TimelineStore | undefined {
    return this.stores.get(key);
  }

  add(key: string, store: TimelineStore) {
    this.stores.set(key, store);
  }

  hold(key: string) {
    this.held.add(key);
  }

  letGo(key: string) {
    this.held.delete(key);
    this.release(key);
  }

  /** Frees the store once nothing uses it, unless the cache holds its record's complete entry. */
  release(key: string) {
    const store = this.stores.get(key);
    if (store && !this.inUse(key, store) && !isCached(store)) this.drop(key, store);
  }

  private dropIdle(doc: string) {
    for (const [key, store] of this.stores) {
      if (store.doc === doc && !this.inUse(key, store)) this.drop(key, store);
    }
  }

  private inUse(key: string, store: TimelineStore): boolean {
    return store.mounted > 0 || this.held.has(key);
  }

  private drop(key: string, store: TimelineStore) {
    this.stores.delete(key);
    store.dispose();
  }
}

function isCached(store: TimelineStore): boolean {
  return readCachedDocument(store.doctype, store.docname)?.complete === true;
}
