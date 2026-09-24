// A list's rows as one array, handed out again while the list and its documents are unchanged.
import type { DocumentRecord } from "../api";
import type { DocumentEntry, ListEntry } from "./entries";

interface Held {
  list: ListEntry;
  entries: readonly (DocumentEntry | undefined)[];
  rows: DocumentRecord[];
}

export class RowsMemo {
  private held = new Map<string, Held>();

  rows(list: ListEntry, entries: (DocumentEntry | undefined)[]): DocumentRecord[] {
    const held = this.held.get(list.key);
    if (held && held.list === list && sameItems(held.entries, entries)) return held.rows;
    const docs = entries.flatMap((entry) => (entry ? [entry.doc as DocumentRecord] : []));
    const rows = Object.freeze(docs) as DocumentRecord[];
    this.held.set(list.key, { list, entries, rows });
    return rows;
  }

  get size(): number {
    return this.held.size;
  }

  forget(key: string): void {
    this.held.delete(key);
  }

  clear(): void {
    this.held.clear();
  }
}

function sameItems<T>(first: readonly T[], second: readonly T[]): boolean {
  return first.length === second.length && first.every((item, index) => item === second[index]);
}
