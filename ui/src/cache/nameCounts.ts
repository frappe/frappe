// How many list entries name each document, so a lookup does not walk every list.
import { documentKey } from "./entries";

export class NameCounts {
  private counts = new Map<string, number>();

  has(key: string): boolean {
    return this.counts.has(key);
  }

  add(doctype: string, names: readonly string[]): void {
    for (const name of names) {
      const key = documentKey(doctype, name);
      this.counts.set(key, (this.counts.get(key) ?? 0) + 1);
    }
  }

  remove(doctype: string, names: readonly string[]): void {
    for (const name of names) {
      const key = documentKey(doctype, name);
      const count = (this.counts.get(key) ?? 0) - 1;
      if (count > 0) this.counts.set(key, count);
      else this.counts.delete(key);
    }
  }

  clear(): void {
    this.counts.clear();
  }
}
