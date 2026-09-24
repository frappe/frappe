// One entry per document and per list query; every feed applies its whole reply in one call.
import type { DocumentRecord, Envelope, ListEnvelope, ListQuery } from "../api";
import { isApiError } from "../api/envelope";
import {
  compareModified,
  documentEntry,
  documentKey,
  frozenCopy,
  hasName,
  holdsEveryPart,
  listEntry,
  withPartField,
  withoutName,
  type DocumentEntry,
  type ListEntry,
} from "./entries";
import { isFeedableQuery, listCacheKey } from "./listKey";
import { NameCounts } from "./nameCounts";
import { RowsMemo } from "./rowsMemo";
import { WriteGate } from "./writeGate";

const COMPLETE_LIMIT = 50;
const LIST_LIMIT = 20;

export class DataCache {
  private documents = new Map<string, DocumentEntry>();
  private lists = new Map<string, ListEntry>();
  private named = new NameCounts();
  // Least recently read first.
  private readRecords = new Set<string>();
  private readLists = new Set<string>();
  private gate = new WriteGate({
    hasDocument: (key) => this.documents.has(key),
    hasList: (key) => this.lists.has(key),
  });
  private memo = new RowsMemo();
  private changeCount = 0;

  /** Grows on every change to an entry, so a caller can tell whether a feed changed anything. */
  get changes(): number {
    return this.changeCount;
  }

  document(doctype: string, name: string): DocumentEntry | undefined {
    return this.documents.get(documentKey(doctype, name));
  }

  list(key: string): ListEntry | undefined {
    return this.lists.get(key);
  }

  /** The list's rows, each read from its document entry, in list order; frozen. */
  rows(key: string): DocumentRecord[] | undefined {
    const list = this.lists.get(key);
    if (!list) return undefined;
    return this.memo.rows(list, list.names.map((name) => this.document(list.doctype, name)));
  }

  takeTicket(): number {
    return this.gate.next();
  }

  settleTicket(ticket: number): void {
    this.gate.settle(ticket);
  }

  /** The entry is complete once it holds every record part; a narrower read is no visit. */
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
    const order = entry ? compareModified(doc, entry.doc) : 1;
    if (order < 0) return;
    const carried = recordParts(envelope, include);
    const parts = entry && order === 0 ? { ...entry.parts, ...carried } : carried;
    const complete = holdsEveryPart(parts);
    if (!complete && !this.named.has(key)) return this.dropDocument(key);
    this.setDocument(key, documentEntry(doctype, frozenCopy(doc), complete, parts), ticket);
    if (!complete) this.readRecords.delete(key);
    else if (!entry?.complete || holdsEveryPart(carried)) this.visitRecord(key);
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
    if (!this.gate.admitList(key, ticket)) return this.applyOlderRows(ticket, doctype, rows);
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
    if (entry) this.replaceDoc(key, entry, doc, ticket);
  }

  /** A method's `docs` hold unsaved documents too; only a save moves `modified` forward. */
  docsWrite(ticket: number, doctype: string, doc: DocumentRecord) {
    if (!hasName(doc)) return;
    const key = documentKey(doctype, String(doc.name));
    const entry = this.documents.get(key);
    if (!entry || compareModified(doc, entry.doc) <= 0) return;
    if (this.gate.admitWrite(key, ticket)) this.replaceDoc(key, entry, doc, ticket);
  }

  /** A write sent after the delete landed first: the document was made again. */
  delete(ticket: number, doctype: string, name: string) {
    const key = documentKey(doctype, name);
    if (this.gate.writtenAfter(key, ticket)) return;
    this.gate.seal(key);
    this.dropDocument(key);
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
    const holds = entry.complete || part in entry.parts;
    const doc = withPartField(entry.doc, part, value);
    if (!holds && doc === entry.doc) return;
    const parts = holds ? { ...entry.parts, [part]: frozenCopy(value) } : entry.parts;
    this.setDocument(key, documentEntry(doctype, doc, entry.complete, parts), ticket);
  }

  /** The server may hold the name in another case, so every entry matching it goes. */
  readError(ticket: number, doctype: string, name: string, error: unknown) {
    if (!isApiError(error) || (error.status !== 403 && error.status !== 404)) return;
    const lowered = String(name).toLowerCase();
    const matching = [...this.documents.values()].filter(
      (entry) => entry.doctype === doctype && entry.name.toLowerCase() === lowered
    );
    for (const entry of matching) {
      const key = documentKey(doctype, entry.name);
      if (this.gate.newerThanEntry(key, ticket)) this.dropDocument(key);
    }
  }

  clear() {
    if (this.documents.size || this.lists.size) this.changeCount++;
    this.documents.clear();
    this.lists.clear();
    this.named.clear();
    this.readRecords.clear();
    this.readLists.clear();
    this.gate.clear();
    this.memo.clear();
  }

  /** For tests: how many keys the entries, the gate and the rows memo hold. */
  sizes() {
    const entries = { documents: this.documents.size, lists: this.lists.size };
    return { ...entries, ...this.gate.sizes(), memo: this.memo.size };
  }

  /** Whether the list keeps naming the row's document. */
  private applyRow(ticket: number, doctype: string, row: DocumentRecord): boolean {
    const key = documentKey(doctype, String(row.name));
    if (!this.gate.admitRead(key, ticket)) return !this.gate.isSealed(key);
    const entry = this.documents.get(key);
    if (!entry || compareModified(row, entry.doc) > 0) {
      this.setDocument(key, documentEntry(doctype, frozenCopy(row), false), ticket);
      this.readRecords.delete(key);
    } else if (compareModified(row, entry.doc) === 0) {
      const doc = Object.freeze({ ...entry.doc, ...frozenCopy(row) });
      this.setDocument(key, documentEntry(doctype, doc, entry.complete, entry.parts), ticket);
    }
    return true;
  }

  /** The list keeps the newer reply's names; the rows still update the documents held. */
  private applyOlderRows(ticket: number, doctype: string, rows: DocumentRecord[]) {
    for (const row of rows) this.applyRow(ticket, doctype, row);
    this.dropUnnamed(doctype, rows.map((row) => String(row.name)));
  }

  private replaceDoc(key: string, entry: DocumentEntry, doc: DocumentRecord, ticket: number) {
    const replaced = documentEntry(entry.doctype, frozenCopy(doc), entry.complete, entry.parts);
    this.setDocument(key, replaced, ticket);
  }

  private visitRecord(key: string) {
    touch(this.readRecords, key);
    this.evictRecords();
  }

  private setDocument(key: string, entry: DocumentEntry, ticket?: number) {
    this.documents.set(key, entry);
    if (ticket !== undefined) this.gate.land(key, ticket);
    this.changeCount++;
  }

  private dropDocument(key: string) {
    if (this.documents.delete(key)) {
      this.changeCount++;
      this.gate.documentLeft(key);
    }
    this.readRecords.delete(key);
  }

  private setList(list: ListEntry) {
    const previous = this.lists.get(list.key);
    this.named.add(list.doctype, list.names);
    if (previous) this.named.remove(previous.doctype, previous.names);
    this.lists.set(list.key, list);
    this.changeCount++;
  }

  private removeList(key: string): ListEntry | undefined {
    const list = this.lists.get(key);
    if (!list) return undefined;
    this.lists.delete(key);
    this.named.remove(list.doctype, list.names);
    this.gate.listLeft(key);
    this.memo.forget(key);
    this.changeCount++;
    return list;
  }

  private evictRecords() {
    for (const key of this.readRecords) {
      if (this.readRecords.size <= COMPLETE_LIMIT) return;
      this.readRecords.delete(key);
      const entry = this.documents.get(key);
      if (!entry) continue;
      if (this.named.has(key)) {
        this.setDocument(key, documentEntry(entry.doctype, entry.doc, false));
      } else {
        this.dropDocument(key);
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
      if (entry && !entry.complete && !this.named.has(key)) this.dropDocument(key);
    }
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

function touch(recent: Set<string>, key: string) {
  recent.delete(key);
  recent.add(key);
}
