// The shared data cache: the API wrapper feeds it, and pages read documents and lists from it.
import { shallowRef } from "vue";
import type { DocumentRecord, Envelope, ListEnvelope, ListQuery } from "../api";
import { DataCache } from "./dataCache";
import type { DocumentEntry, ListEntry } from "./entries";
import { listCacheKey } from "./listKey";

export type { DocumentEntry, ListEntry } from "./entries";
export { RECORD_PARTS } from "./entries";
export { listCacheKey } from "./listKey";

const cache = new DataCache();
// The maps are plain and this counter moves once per feed, so a sync watcher sees a whole reply.
const version = shallowRef(0);

/** Reactive: a `computed` over it re-runs when the entry changes. */
export function readCachedDocument(doctype: string, name: string): DocumentEntry | undefined {
  track();
  return cache.document(doctype, name);
}

export function readCachedList(doctype: string, query: ListQuery): ListEntry | undefined {
  track();
  return cache.list(listCacheKey(doctype, query));
}

/** The list's rows, each read from its document entry, in list order; frozen. */
export function readCachedRows(doctype: string, query: ListQuery): DocumentRecord[] | undefined {
  track();
  return cache.rows(listCacheKey(doctype, query));
}

export function clearDataCache(): void {
  feed(() => cache.clear());
}

/** Taken when a request is sent, not when its reply lands. */
export function takeTicket(): number {
  return cache.takeTicket();
}

/** Once per ticket, after the request's reply or failure has been fed. */
export function settleTicket(ticket: number): void {
  cache.settleTicket(ticket);
}

export function feedRecordRead(
  ticket: number,
  doctype: string,
  envelope: Envelope<DocumentRecord>,
  include: readonly string[]
): void {
  feed(() => cache.recordRead(ticket, doctype, envelope, include));
}

export function feedListRead(
  ticket: number,
  doctype: string,
  query: ListQuery,
  envelope: ListEnvelope<DocumentRecord>
): void {
  feed(() => cache.listRead(ticket, doctype, query, envelope));
}

/** A save or a create. */
export function feedDocumentWrite(ticket: number, doctype: string, doc: DocumentRecord): void {
  feed(() => cache.documentWrite(ticket, doctype, doc));
}

/** One document of a reply's `docs`, which a method may send back unsaved. */
export function feedDocsDocument(ticket: number, doctype: string, doc: DocumentRecord): void {
  feed(() => cache.docsWrite(ticket, doctype, doc));
}

export function feedDelete(ticket: number, doctype: string, name: string): void {
  feed(() => cache.delete(ticket, doctype, name));
}

/** A part write's reply: the refreshed part. */
export function feedPartWrite(
  ticket: number,
  doctype: string,
  name: string,
  part: string,
  value: unknown
): void {
  feed(() => cache.partWrite(ticket, doctype, name, part, value));
}

/** A 403 or 404 on a record read. */
export function feedReadError(ticket: number, doctype: string, name: string, error: unknown): void {
  feed(() => cache.readError(ticket, doctype, name, error));
}

function track(): number {
  return version.value;
}

function feed(apply: () => void): void {
  const before = cache.changes;
  try {
    apply();
  } finally {
    if (cache.changes !== before) version.value++;
  }
}
