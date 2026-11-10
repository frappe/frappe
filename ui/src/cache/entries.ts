// The frozen entries the cache holds, and how a reply's values become part of one.
import type { DocumentRecord, ListEnvelope } from "../api";
import { NO_JOINS, type Joins } from "./joins";

/** The parts beside the document; an entry holding all of them is complete. */
export const RECORD_PARTS = [
  "permissions",
  "assignments",
  "shares",
  "tags",
  "favourites",
  "follows",
  "users",
  "link_titles",
  "link_marks",
  "attachments",
] as const;

export interface DocumentEntry {
  readonly doctype: string;
  readonly name: string;
  /** A partial entry can hold fields older than its `modified`, so never save from it. */
  readonly doc: Readonly<DocumentRecord>;
  /** True after a record read; a list row or a save alone leaves an entry partial. */
  readonly complete: boolean;
  /** The side parts of the record read (permissions, attachments, assignments, ... link_titles), never `seen`. */
  readonly parts: Readonly<Record<string, unknown>>;
  /** The join values the doc holds from a list read, each with its link; a full record read keeps them. */
  readonly joins: Joins;
}

export interface ListEntry {
  readonly key: string;
  readonly doctype: string;
  readonly names: readonly string[];
  readonly hasNextPage: boolean;
  readonly count: number | null | undefined;
  readonly countCapped: boolean;
}

type PartField = { field: string; format: (value: unknown[]) => string };

/** The document column the server writes beside a part, in the server's format. */
const PART_FIELDS: Record<string, PartField> = {
  assignments: { field: "_assign", format: (rows) => pythonJsonList(rows.map(assignedUser)) },
  tags: { field: "_user_tags", format: (tags) => tags.join(",") },
  seen: { field: "_seen", format: (users) => pythonJsonList(users as string[]) },
};

/** `frappe.model.optional_fields`: `as_dict` drops them, so only a list read or a part write sets them. */
export const LIST_ONLY_FIELDS: readonly string[] = ["_user_tags", "_assign", "_liked_by", "_seen"];

export function documentKey(doctype: string, name: string): string {
  return `${doctype}\u0000${name}`;
}

export function hasName(row: unknown): row is DocumentRecord {
  const name = (row as { name?: unknown } | null)?.name;
  return (typeof name === "string" && name !== "") || typeof name === "number";
}

export function documentEntry(
  doctype: string,
  doc: Readonly<DocumentRecord>,
  complete: boolean,
  parts: Record<string, unknown> = {},
  joins: Joins = NO_JOINS
): DocumentEntry {
  const name = String(doc.name);
  return Object.freeze({ doctype, name, doc, complete, parts: Object.freeze(parts), joins });
}

export function holdsEveryPart(parts: Readonly<Record<string, unknown>>): boolean {
  return RECORD_PARTS.every((part) => part in parts);
}

export function listEntry(
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
export function withoutName(list: ListEntry, name: string): ListEntry {
  const lowered = typeof list.count === "number" && !list.countCapped;
  const count = lowered ? list.count! - 1 : list.count;
  const names = Object.freeze(list.names.filter((listed) => listed !== name));
  return Object.freeze({ ...list, names, count });
}

/** Above zero when `row` is newer; a doc with no `modified` is older than any row. */
export function compareModified(row: DocumentRecord, doc: Readonly<DocumentRecord>): number {
  if (!doc.modified) return 1;
  if (!row.modified) return -1;
  return row.modified === doc.modified ? 0 : row.modified > doc.modified ? 1 : -1;
}

/** The doc with the column a part write also changes on the server, if the part has one. */
export function withPartField(
  doc: Readonly<DocumentRecord>,
  part: string,
  value: unknown
): Readonly<DocumentRecord> {
  const partField = PART_FIELDS[part];
  if (!partField || !Array.isArray(value)) return doc;
  return Object.freeze({ ...doc, [partField.field]: partField.format(value) });
}

/** The doc with the list-only columns it leaves out, taken from the entry it replaces. */
export function withListColumns(
  doc: Readonly<DocumentRecord>,
  previous: Readonly<DocumentRecord> | undefined
): Readonly<DocumentRecord> {
  const kept: Record<string, unknown> = {};
  for (const field of LIST_ONLY_FIELDS) if (previous && field in previous) kept[field] = previous[field];
  return Object.freeze({ ...kept, ...doc });
}

/** The reply's parts refresh the list-only columns the doc holds; `seen` is no part but always sets its column. */
export function withPartFields(
  doc: Readonly<DocumentRecord>,
  envelope: Readonly<Record<string, unknown>>,
  include: readonly string[]
): Readonly<DocumentRecord> {
  for (const part of include) {
    const field = PART_FIELDS[part]?.field;
    if (part in envelope && field && (part === "seen" || field in doc)) {
      doc = withPartField(doc, part, envelope[part]);
    }
  }
  return doc;
}

/** A deep copy the cache owns: the wrapper hands the reply itself back to its caller. */
export function frozenCopy<T>(value: T): T {
  if (Array.isArray(value)) return Object.freeze(value.map(frozenCopy)) as T;
  if (!isPlainObject(value)) return value;
  const copy: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value)) copy[key] = frozenCopy(item);
  return Object.freeze(copy) as T;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return (
    value !== null && typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype
  );
}

function assignedUser(row: unknown): string {
  return String((row as { user?: unknown } | null)?.user ?? "");
}

/** Python's `json.dumps`: `", "` between items, non-ASCII escaped; an empty list is `""`. */
function pythonJsonList(items: string[]): string {
  if (!items.length) return "";
  const quoted = items.map((item) =>
    JSON.stringify(item).replace(/[\u0080-\uffff]/g, unicodeEscape)
  );
  return `[${quoted.join(", ")}]`;
}

function unicodeEscape(character: string): string {
  return `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`;
}
