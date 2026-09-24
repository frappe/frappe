// The frozen entries the cache holds, and how a reply's values become part of one.
import type { DocumentRecord } from "../api";

export interface DocumentEntry {
  readonly doctype: string;
  readonly name: string;
  readonly doc: Readonly<DocumentRecord>;
  /** True after a record read; a list row or a save alone leaves an entry partial. */
  readonly complete: boolean;
  /** The side parts of the record read (permissions, attachments, assignments, ... link_titles), never `seen`. */
  readonly parts: Readonly<Record<string, unknown>>;
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
};

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
  parts: Record<string, unknown> = {}
): DocumentEntry {
  const name = String(doc.name);
  return Object.freeze({ doctype, name, doc, complete, parts: Object.freeze(parts) });
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
