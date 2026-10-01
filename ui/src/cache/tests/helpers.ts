// Replies shaped like the wrapper's, fed the way the wrapper feeds them.
import type { DocumentRecord, ListEnvelope, ListQuery } from "../../api";
import { RECORD_PARTS, feedListRead, feedRecordRead, takeTicket } from "../index";

export const DOCTYPE = "ToDo";
export const OLD = "2026-09-01 10:00:00.000000";
export const MIDDLE = "2026-09-02 10:00:00.000000";
export const NEW = "2026-09-03 10:00:00.000000";

export function doc(name: string, modified?: string, fields: Record<string, unknown> = {}) {
  return { name, ...(modified ? { modified } : {}), ...fields } as DocumentRecord;
}

/** A small reply, so only the count limits the complete records. */
export const REPLY_SIZE = 1000;
export const MB = 1024 * 1024;

export const PERMISSIONS = { permissions: { read: 1 } };

/** A value for every record part. */
export const ALL_PARTS: Record<string, unknown> = {
  ...Object.fromEntries(RECORD_PARTS.map((part) => [part, []])),
  ...PERMISSIONS,
};

/** A record read asks for every record part; `parts` overrides some of their values. */
export function readRecord(
  record: DocumentRecord,
  parts: Record<string, unknown> = {},
  ticket = takeTicket(),
  replySize = REPLY_SIZE
) {
  readSomeParts(record, { ...ALL_PARTS, ...parts }, ticket, replySize);
}

export function readSomeParts(
  record: DocumentRecord,
  parts: Record<string, unknown>,
  ticket = takeTicket(),
  replySize = REPLY_SIZE
) {
  feedRecordRead(ticket, DOCTYPE, { data: record, ...parts }, Object.keys(parts), replySize);
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
