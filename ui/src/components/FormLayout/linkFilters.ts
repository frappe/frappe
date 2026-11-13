import { evaluateValue } from "./dependsOn";

/** Link search filters, `{ fieldname: [operator, value] }`, as the search and `validate_link_and_fetch` take them. */
export type LinkFilters = Record<string, [string, unknown]>;

/**
 * A DocField's `link_filters` as Link search filters, each `eval:` value read
 * from the record as desk v1's `link.js` does. `undefined` when there are none.
 */
export function resolveLinkFilters(
  stored: string | unknown[] | undefined,
  doc: Record<string, any>,
  parent: Record<string, any> = doc
): LinkFilters | undefined {
  const rows = parseLinkFilters(stored);
  if (!rows.length) return undefined;
  return Object.fromEntries(
    rows.map(([, fieldname, operator, value]) => [
      String(fieldname),
      [String(operator), resolveValue(value, doc, parent)],
    ])
  );
}

function parseLinkFilters(stored: string | unknown[] | undefined): unknown[][] {
  let rows: unknown = stored;
  if (typeof stored === "string") {
    try {
      rows = JSON.parse(stored);
    } catch {
      return [];
    }
  }
  return Array.isArray(rows)
    ? rows.filter((row): row is unknown[] => Array.isArray(row) && row.length >= 4)
    : [];
}

// An unset `doc.x` would vanish from the JSON and leave the operator alone on the wire.
function resolveValue(value: unknown, doc: Record<string, any>, parent: Record<string, any>) {
  if (typeof value !== "string" || !value.startsWith("eval:")) return value;
  return evaluateValue(value.slice(5), doc, parent) ?? null;
}
