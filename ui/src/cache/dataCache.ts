// One entry per document and per list query; every feed applies its whole reply in one call.
import { shallowReactive } from "vue";
import type { DocumentRecord, Envelope, ListEnvelope, ListQuery } from "../api";
import { isApiError } from "../api/envelope";
import {
  compareModified,
  documentEntry,
  documentKey,
  frozenCopy,
  hasName,
  withPartField,
  type DocumentEntry,
  type ListEntry,
} from "./entries";
import { isFeedableQuery, listCacheKey } from "./listKey";
import { NameCounts } from "./nameCounts";
import { WriteGate } from "./writeGate";

const COMPLETE_LIMIT = 50;
const LIST_LIMIT = 20;

export class DataCache {
  private documents = shallowReactive(new Map<string, DocumentEntry>());
  private lists = shallowReactive(new Map<string, ListEntry>());
  private named = new NameCounts();
  // Least recently read first.
  private readRecords = new Set<string>();
  private readLists = new Set<string>();
  private gate = new WriteGate();

  document(doctype: string, name: string): DocumentEntry | undefined {
    return this.documents.get(documentKey(doctype, name));
  }

  list(key: string): ListEntry | undefined {
    return this.lists.get(key);
  }

  takeTicket(): number {
    return this.gate.next();
  }

  /** Only a read that asks for parts makes the entry complete. */
  recordRead(
    ticket: number,
    doctype: string,
    envelope: Envelope<DocumentRecord>,
    include: readonly string[]
  ) {
    const doc = envelope.data;
    if (!hasName(doc)) return;
    const key = documentKey(doctype, String(doc.name));
    const entry = this.documents.get(key);
    if (!this.gate.admitRead(key, ticket)) return;
    if (entry && compareModified(doc, entry.doc) < 0) return;
    if (!include.some((part) => part !== "seen")) {
      if (entry) this.replaceDoc(key, entry, doc);
      return;
    }
    const parts = recordParts(envelope, include);
    this.documents.set(key, documentEntry(doctype, frozenCopy(doc), true, parts));
    touch(this.readRecords, key);
    this.evictRecords();
  }

  listRead(
    ticket: number,
    doctype: string,
    query: ListQuery,
    envelope: ListEnvelope<DocumentRecord>
  ) {
    const rows = envelope.data;
    if (!this.gate.current(ticket) || !isFeedable(query, rows)) return;
    const key = listCacheKey(doctype, query);
    const previous = this.lists.get(key);
    const start = query.start ?? 0;
    if (start > (previous?.names.length ?? 0)) return;
    const listed = rows.filter((row) => this.applyRow(ticket, doctype, row));
    const kept = previous ? previous.names.slice(0, start) : [];
    const names = [...new Set([...kept, ...listed.map((row) => String(row.name))])];
    this.setList(listEntry(key, doctype, names, envelope, previous));
    if (previous) this.dropUnnamed(doctype, previous.names);
    touch(this.readLists, key);
    this.evictLists();
  }

  /** A save or a create. */
  documentWrite(ticket: number, doctype: string, doc: DocumentRecord) {
    if (!hasName(doc)) return;
    const key = documentKey(doctype, String(doc.name));
    if (!this.gate.admitWrite(key, ticket)) return;
    const entry = this.documents.get(key);
    if (entry) this.replaceDoc(key, entry, doc);
  }

  /** A method's `docs` hold unsaved documents too; only a save moves `modified` forward. */
  docsWrite(ticket: number, doctype: string, doc: DocumentRecord) {
    if (!hasName(doc)) return;
    const key = documentKey(doctype, String(doc.name));
    const entry = this.documents.get(key);
    if (!entry || compareModified(doc, entry.doc) <= 0) return;
    if (this.gate.admitWrite(key, ticket)) this.replaceDoc(key, entry, doc);
  }

  delete(doctype: string, name: string) {
    const key = documentKey(doctype, name);
    this.gate.seal(key);
    this.removeDocument(key);
    if (!this.named.has(key)) return;
    for (const list of this.lists.values()) {
      if (list.doctype === doctype && list.names.includes(name)) {
        this.setList(withoutName(list, name));
      }
    }
  }

  partWrite(ticket: number, doctype: string, name: string, part: string, value: unknown) {
    const key = documentKey(doctype, name);
    if (!this.gate.admitWrite(key, ticket)) return;
    const entry = this.documents.get(key);
    if (!entry) return;
    const doc = withPartField(entry.doc, part, value);
    if (!entry.complete && doc === entry.doc) return;
    const parts = entry.complete ? { ...entry.parts, [part]: frozenCopy(value) } : entry.parts;
    this.documents.set(key, documentEntry(doctype, doc, entry.complete, parts));
  }

  /** The server may hold the name in another case, so every entry matching it goes. */
  readError(doctype: string, name: string, error: unknown) {
    if (!isApiError(error) || (error.status !== 403 && error.status !== 404)) return;
    const lowered = String(name).toLowerCase();
    const matching = [...this.documents.values()].filter(
      (entry) => entry.doctype === doctype && entry.name.toLowerCase() === lowered
    );
    for (const entry of matching) this.removeDocument(documentKey(doctype, entry.name));
  }

  clear() {
    this.documents.clear();
    this.lists.clear();
    this.named.clear();
    this.readRecords.clear();
    this.readLists.clear();
    this.gate.clear();
  }

  /** Whether the list keeps naming the row's document. */
  private applyRow(ticket: number, doctype: string, row: DocumentRecord): boolean {
    const key = documentKey(doctype, String(row.name));
    if (!this.gate.admitRead(key, ticket)) return !this.gate.isSealed(key);
    const entry = this.documents.get(key);
    if (!entry || compareModified(row, entry.doc) > 0) {
      this.documents.set(key, documentEntry(doctype, frozenCopy(row), false));
      this.readRecords.delete(key);
    } else if (compareModified(row, entry.doc) === 0) {
      const doc = Object.freeze({ ...entry.doc, ...frozenCopy(row) });
      this.documents.set(key, documentEntry(doctype, doc, entry.complete, entry.parts));
    }
    return true;
  }

  private replaceDoc(key: string, entry: DocumentEntry, doc: DocumentRecord) {
    const replaced = documentEntry(entry.doctype, frozenCopy(doc), entry.complete, entry.parts);
    this.documents.set(key, replaced);
  }

  private setList(list: ListEntry) {
    const previous = this.lists.get(list.key);
    this.named.add(list.doctype, list.names);
    if (previous) this.named.remove(previous.doctype, previous.names);
    this.lists.set(list.key, list);
  }

  private removeList(key: string): ListEntry | undefined {
    const list = this.lists.get(key);
    if (!list) return undefined;
    this.lists.delete(key);
    this.named.remove(list.doctype, list.names);
    return list;
  }

  private evictRecords() {
    for (const key of this.readRecords) {
      if (this.readRecords.size <= COMPLETE_LIMIT) return;
      this.readRecords.delete(key);
      const entry = this.documents.get(key);
      if (!entry) continue;
      if (this.named.has(key)) {
        this.documents.set(key, documentEntry(entry.doctype, entry.doc, false));
      } else {
        this.documents.delete(key);
      }
    }
  }

  private evictLists() {
    for (const key of this.readLists) {
      if (this.readLists.size <= LIST_LIMIT) return;
      this.readLists.delete(key);
      const list = this.removeList(key);
      if (list) this.dropUnnamed(list.doctype, list.names);
    }
  }

  /** Removes each partial entry among `names` that no list names any more. */
  private dropUnnamed(doctype: string, names: readonly string[]) {
    for (const name of names) {
      const key = documentKey(doctype, name);
      const entry = this.documents.get(key);
      if (entry && !entry.complete && !this.named.has(key)) this.documents.delete(key);
    }
  }

  private removeDocument(key: string) {
    this.documents.delete(key);
    this.readRecords.delete(key);
  }
}

function isFeedable(query: ListQuery, rows: unknown): rows is DocumentRecord[] {
  return isFeedableQuery(query) && Array.isArray(rows) && rows.every(hasName);
}

function recordParts(envelope: Envelope<DocumentRecord>, include: readonly string[]) {
  const parts: Record<string, unknown> = {};
  for (const part of include) {
    if (part !== "seen" && part in envelope) parts[part] = frozenCopy(envelope[part]);
  }
  return parts;
}

function listEntry(
  key: string,
  doctype: string,
  names: string[],
  envelope: ListEnvelope<DocumentRecord>,
  previous: ListEntry | undefined
): ListEntry {
  const counted = "count" in envelope;
  return Object.freeze({
    key,
    doctype,
    names: Object.freeze(names),
    hasNextPage: Boolean(envelope.has_next_page),
    count: counted ? (envelope.count ?? null) : previous?.count,
    countCapped: counted ? Boolean(envelope.count_capped) : (previous?.countCapped ?? false),
  });
}

/** A capped count is a floor, not a total, so a delete leaves it as it is. */
function withoutName(list: ListEntry, name: string): ListEntry {
  const lowered = typeof list.count === "number" && !list.countCapped;
  const count = lowered ? list.count! - 1 : list.count;
  const names = Object.freeze(list.names.filter((listed) => listed !== name));
  return Object.freeze({ ...list, names, count });
}

function touch(recent: Set<string>, key: string) {
  recent.delete(key);
  recent.add(key);
}
