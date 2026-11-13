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
  const filters: LinkFilters = {};
  for (const [, fieldname, operator, value] of parseLinkFilters(stored)) {
    try {
      filters[String(fieldname)] = [String(operator), resolveValue(value, doc, parent)];
    } catch {
      // Left out: as null it would match only records with that field empty.
      continue;
    }
  }
  return Object.keys(filters).length ? filters : undefined;
}

/**
 * A script's filters with the DocField's own over them, as desk v1's `link.js`
 * merges them: an object by key, a list by dropping the rows they replace.
 */
export function mergeLinkFilters(
  script: Record<string, unknown> | unknown[] | undefined,
  own: LinkFilters,
  doctype?: string
): Record<string, unknown> {
  if (!Array.isArray(script)) return { ...script, ...own };
  // A script may pass v1's list form, which `filters`' type does not name.
  const replaced = (row: unknown) => {
    if (!Array.isArray(row)) return false;
    const [rowDoctype, fieldname] = row.length >= 4 ? row : [doctype, row[0]];
    return rowDoctype === doctype && String(fieldname) in own;
  };
  return script
    .filter((row) => !replaced(row))
    .concat(Object.entries(own).map(([fieldname, rule]) => [fieldname, ...rule])) as unknown as Record<string, unknown>;
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

function resolveValue(value: unknown, doc: Record<string, any>, parent: Record<string, any>) {
  if (typeof value !== "string" || !value.startsWith("eval:")) return value;
  return evaluateValue(value.slice(5), doc, parent) ?? null;
}
