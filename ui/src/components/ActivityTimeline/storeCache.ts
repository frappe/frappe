import type { TimelineStore } from "./timelineStore";

// idle stores kept so reopening a doc is instant; past this, the least recently used goes
const IDLE_STORES = 20;

/** Stores by cache key, most recently used last. */
export class StoreCache {
  private readonly stores = new Map<string, TimelineStore>();

  get(key: string): TimelineStore | undefined {
    const store = this.stores.get(key);
    if (!store) return undefined;
    this.stores.delete(key);
    this.stores.set(key, store);
    return store;
  }

  add(key: string, store: TimelineStore) {
    this.stores.set(key, store);
    this.evictIdle();
  }

  evictIdle() {
    const idle = [...this.stores].filter(([, store]) => !store.mounted);
    for (const [key, store] of idle.slice(0, -IDLE_STORES)) {
      this.stores.delete(key);
      store.dispose();
    }
  }
}
