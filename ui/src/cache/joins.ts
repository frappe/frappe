// Join fields a list reads (`link.field as alias`): which link each alias hangs on, and when its value still holds.
import type { DocumentRecord } from "../api";

/** Alias to the Link field the value was read through. */
export type Joins = Readonly<Record<string, string>>;

const WORD = "[A-Za-z0-9_]+";
export const JOIN_FIELD = new RegExp(`^(${WORD})\\.${WORD} as (${WORD})$`);

export const NO_JOINS: Joins = Object.freeze({});

export function joinsOf(fields: readonly string[] = []): Joins {
  const joins: Record<string, string> = {};
  for (const field of fields) {
    const match = JOIN_FIELD.exec(field);
    if (match) joins[match[2]] = match[1];
  }
  return joins;
}

/** `doc` with the values of `previous` it lacks, kept only while their link holds the same name. */
export function carryJoins(
  doc: Readonly<DocumentRecord>,
  previous: { doc: Readonly<DocumentRecord>; joins: Joins } | undefined,
  added: Joins = NO_JOINS
): { doc: Readonly<DocumentRecord>; joins: Joins } {
  const joins: Record<string, string> = { ...added };
  const kept: Record<string, unknown> = {};
  for (const [alias, link] of Object.entries(previous?.joins ?? {})) {
    if (alias in added || !(alias in previous!.doc) || !holds(doc, previous!.doc, link)) continue;
    kept[alias] = previous!.doc[alias];
    joins[alias] = link;
  }
  return { doc: Object.freeze({ ...doc, ...kept }), joins: Object.freeze(joins) };
}

/** A link the list did not read cannot be compared, so the value holds only for the same `modified`. */
function holds(doc: Readonly<DocumentRecord>, previous: Readonly<DocumentRecord>, link: string) {
  if (link in previous) return doc[link] === previous[link];
  return doc.modified !== undefined && doc.modified === previous.modified;
}

export function withoutJoins(doc: Readonly<DocumentRecord>, joins: Joins): Readonly<DocumentRecord> {
  const rest: DocumentRecord = { ...doc };
  for (const alias of Object.keys(joins)) delete rest[alias];
  return Object.freeze(rest);
}
