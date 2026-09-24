// The shared data cache: the API wrapper feeds it, and pages read documents and lists from it.
import type { DocumentRecord, Envelope, ListEnvelope, ListQuery } from "../api";
import { DataCache } from "./dataCache";
import type { DocumentEntry, ListEntry } from "./entries";
import { listCacheKey } from "./listKey";

export type { DocumentEntry, ListEntry } from "./entries";
export { listCacheKey } from "./listKey";

const cache = new DataCache();

/** Reactive: a `computed` over it re-runs when the entry changes. */
export function readCachedDocument(doctype: string, name: string): DocumentEntry | undefined {
  return cache.document(doctype, name);
}

export function readCachedList(doctype: string, query: ListQuery): ListEntry | undefined {
  return cache.list(listCacheKey(doctype, query));
}

/** The list's rows, each read from its document entry, in list order. */
export function readCachedRows(doctype: string, query: ListQuery): DocumentRecord[] | undefined {
  const list = readCachedList(doctype, query);
  if (!list) return undefined;
  return list.names.flatMap((name) => {
    const entry = cache.document(doctype, name);
    return entry ? [entry.doc as DocumentRecord] : [];
  });
}

export function clearDataCache(): void {
  cache.clear();
}

/** Taken when a request is sent, not when its reply lands. */
export function takeTicket(): number {
  return cache.takeTicket();
}

export function feedRecordRead(
  ticket: number,
  doctype: string,
  envelope: Envelope<DocumentRecord>,
  include: readonly string[]
): void {
  cache.recordRead(ticket, doctype, envelope, include);
}

export function feedListRead(
  ticket: number,
  doctype: string,
  query: ListQuery,
  envelope: ListEnvelope<DocumentRecord>
): void {
  cache.listRead(ticket, doctype, query, envelope);
}

/** A save or a create. */
export function feedDocumentWrite(ticket: number, doctype: string, doc: DocumentRecord): void {
  cache.documentWrite(ticket, doctype, doc);
}

/** One document of a reply's `docs`, which a method may send back unsaved. */
export function feedDocsDocument(ticket: number, doctype: string, doc: DocumentRecord): void {
  cache.docsWrite(ticket, doctype, doc);
}

export function feedDelete(doctype: string, name: string): void {
  cache.delete(doctype, name);
}

/** A part write's reply: the refreshed part. */
export function feedPartWrite(
  ticket: number,
  doctype: string,
  name: string,
  part: string,
  value: unknown
): void {
  cache.partWrite(ticket, doctype, name, part, value);
}

/** A 403 or 404 on a record read. */
export function feedReadError(doctype: string, name: string, error: unknown): void {
  cache.readError(doctype, name, error);
}
