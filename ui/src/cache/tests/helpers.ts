// Replies shaped like the wrapper's, fed the way the wrapper feeds them.
import type { DocumentRecord, ListEnvelope, ListQuery } from "../../api";
import { feedListRead, feedRecordRead, takeTicket } from "../index";

export const DOCTYPE = "ToDo";
export const OLD = "2026-09-01 10:00:00.000000";
export const MIDDLE = "2026-09-02 10:00:00.000000";
export const NEW = "2026-09-03 10:00:00.000000";

export function doc(name: string, modified?: string, fields: Record<string, unknown> = {}) {
  return { name, ...(modified ? { modified } : {}), ...fields } as DocumentRecord;
}

/** A record read asks for at least one part, or it leaves the entry partial. */
export const PERMISSIONS = { permissions: { read: 1 } };

export function readRecord(
  record: DocumentRecord,
  parts: Record<string, unknown> = PERMISSIONS,
  ticket = takeTicket()
) {
  feedRecordRead(ticket, DOCTYPE, { data: record, ...parts }, Object.keys(parts));
}

export function readList(
  query: ListQuery,
  rows: unknown[],
  extra: Partial<ListEnvelope<DocumentRecord>> = {},
  ticket = takeTicket()
) {
  const envelope = { data: rows, has_next_page: false, ...extra } as ListEnvelope<DocumentRecord>;
  feedListRead(ticket, DOCTYPE, query, envelope);
}
