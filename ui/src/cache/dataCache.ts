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
import { WriteGate } from "./writeGate";

const COMPLETE_LIMIT = 50;
const LIST_LIMIT = 20;

export class DataCache {
  private documents = shallowReactive(new Map<string, DocumentEntry>());
  private lists = shallowReactive(new Map<string, ListEntry>());
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
    this.documents.set(
      key,
      documentEntry(doctype, frozenCopy(doc), true, recordParts(envelope, include))
    );
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
    if (!isFeedableQuery(query) || !Array.isArray(rows) || !rows.every(hasName)) return;
    const key = listCacheKey(doctype, query);
    const previous = this.lists.get(key);
    const start = query.start ?? 0;
    if (start > 0 && !previous) return;
    const held = rows.filter((row) => this.applyRow(ticket, doctype, row));
    const kept = start > 0 ? previous!.names.slice(0, start) : [];
    const names = [...new Set([...kept, ...held.map((row) => String(row.name))])];
    this.lists.set(key, listEntry(key, doctype, names, envelope, previous));
    if (previous) this.dropUnnamed(doctype, previous.names);
    touch(this.readLists, key);
    this.evictLists();
  }

  documentWrite(ticket: number, doctype: string, doc: DocumentRecord) {
    if (!hasName(doc)) return;
    const key = documentKey(doctype, String(doc.name));
    if (!this.gate.admitWrite(key, ticket)) return;
    const entry = this.documents.get(key);
    if (!entry) return;
    this.documents.set(key, documentEntry(doctype, frozenCopy(doc), entry.complete, entry.parts));
  }

  delete(doctype: string, name: string) {
    const key = documentKey(doctype, name);
    this.gate.seal(key);
    this.removeDocument(key);
    for (const list of this.lists.values()) {
      if (list.doctype === doctype && list.names.includes(name)) {
        this.lists.set(list.key, withoutName(list, name));
      }
    }
  }

  part(ticket: number, doctype: string, name: string, part: string, value: unknown) {
    const key = documentKey(doctype, name);
    const entry = this.documents.get(key);
    if (!entry || !this.gate.admitRead(key, ticket)) return;
    const doc = withPartField(entry.doc, part, value);
    if (!entry.complete && doc === entry.doc) return;
    const parts = entry.complete ? { ...entry.parts, [part]: frozenCopy(value) } : entry.parts;
    this.documents.set(key, documentEntry(doctype, doc, entry.complete, parts));
  }

  readError(doctype: string, name: string, error: unknown) {
    if (isApiError(error) && (error.status === 403 || error.status === 404)) {
      this.removeDocument(documentKey(doctype, name));
    }
  }

  clear() {
    this.documents.clear();
    this.lists.clear();
    this.readRecords.clear();
    this.readLists.clear();
    this.gate.clear();
  }

  /** Whether the document has an entry once the row is applied. */
  private applyRow(ticket: number, doctype: string, row: DocumentRecord): boolean {
    const key = documentKey(doctype, String(row.name));
    const entry = this.documents.get(key);
    if (!this.gate.admitRead(key, ticket)) return Boolean(entry);
    if (!entry || compareModified(row, entry.doc) > 0) {
      this.documents.set(key, documentEntry(doctype, frozenCopy(row), false));
      this.readRecords.delete(key);
    } else if (compareModified(row, entry.doc) === 0) {
      const doc = Object.freeze({ ...entry.doc, ...frozenCopy(row) });
      this.documents.set(key, documentEntry(doctype, doc, entry.complete, entry.parts));
    }
    return true;
  }

  private evictRecords() {
    for (const key of this.readRecords) {
      if (this.readRecords.size <= COMPLETE_LIMIT) return;
      this.readRecords.delete(key);
      const entry = this.documents.get(key);
      if (!entry) continue;
      if (this.isNamed(entry.doctype, entry.name)) {
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
      const list = this.lists.get(key);
      this.lists.delete(key);
      if (list) this.dropUnnamed(list.doctype, list.names);
    }
  }

  /** Removes each partial entry among `names` that no list names any more. */
  private dropUnnamed(doctype: string, names: readonly string[]) {
    for (const name of names) {
      const entry = this.document(doctype, name);
      if (entry && !entry.complete && !this.isNamed(doctype, name)) {
        this.documents.delete(documentKey(doctype, name));
      }
    }
  }

  private isNamed(doctype: string, name: string): boolean {
    for (const list of this.lists.values()) {
      if (list.doctype === doctype && list.names.includes(name)) return true;
    }
    return false;
  }

  private removeDocument(key: string) {
    this.documents.delete(key);
    this.readRecords.delete(key);
  }
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

function withoutName(list: ListEntry, name: string): ListEntry {
  const count = typeof list.count === "number" ? list.count - 1 : list.count;
  const names = Object.freeze(list.names.filter((listed) => listed !== name));
  return Object.freeze({ ...list, names, count });
}

function touch(recent: Set<string>, key: string) {
  recent.delete(key);
  recent.add(key);
}
