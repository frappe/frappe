// What a freshly added child row starts with, from its docfield defaults.
import type { FieldNode, FormLayoutSchema } from "./types";

/**
 * Frappe's own `no_value_fields` (`frappe/model/__init__.py`) minus the two
 * collection types, which DO hold a value in the document even though they have
 * no column of their own — a nested table's empty is `[]`.
 */
const NO_VALUE = new Set([
  "Section Break",
  "Column Break",
  "Tab Break",
  "Heading",
  "HTML",
  "Fold",
  "Button",
  "Image",
  "Attachment Gallery",
]);

const COLLECTIONS = new Set(["Table", "Table MultiSelect"]);

const INTEGERS = new Set(["Int", "Check"]);
const DECIMALS = new Set(["Float", "Currency", "Percent"]);
/**
 * Fieldtypes whose empty is a number rather than a string — every numeric column
 * the server can send back, so `Rating` and `Duration` (both `decimal`) and
 * `Long Int` (`bigint`) belong here too. `Check` is numeric server-side but is
 * seeded `false`; see `emptyValue`.
 */
const NUMBERS = new Set([
  "Int",
  "Long Int",
  "Float",
  "Currency",
  "Percent",
  "Rating",
  "Duration",
]);

/**
 * Seed values for a new row: every field's resolved `default`, plus a Select's
 * first option, which Frappe treats as the default when none is declared.
 *
 * A field with no default still gets a key, holding the *typed* empty for its
 * fieldtype. A row loaded from the server carries every field, typed, so a
 * partial seed would leave a fresh row shaped unlike every other row in the same
 * grid — and a script cannot tell which kind it was handed. `row.qty * row.rate`
 * is then arithmetic, not `NaN`.
 */
export function newRowValues(fields: FieldNode[]): Record<string, any> {
  const row: Record<string, any> = {};
  for (const field of fields) {
    if (NO_VALUE.has(field.fieldtype)) continue;
    row[field.fieldname] = defaultValue(field);
  }
  return row;
}

/** Every field of a child layout, so defaults are not limited to grid columns. */
export function layoutFields(layout: FormLayoutSchema): FieldNode[] {
  return layout.flatMap((tab) =>
    tab.sections.flatMap((section) =>
      section.columns.flatMap((column) => column.fields)
    )
  );
}

function defaultValue(field: FieldNode): any {
  const raw = field.default;
  if (raw == null || raw === "") return firstOption(field) ?? emptyValue(field);
  if (raw === "Today" || raw === "today") return today();
  if (raw === "Now" || raw === "now") return new Date().toISOString().slice(0, 19).replace("T", " ");
  if (INTEGERS.has(field.fieldtype)) return Math.trunc(Number(raw)) || 0;
  if (DECIMALS.has(field.fieldtype)) return Number(raw) || 0;
  return raw;
}

/**
 * The empty a field of this type holds when it declares no default.
 *
 * `Check` is `false` rather than the `0` the server sends, and the date-ish
 * types are `""` rather than the `null` the server sends (`get_valid_dict`
 * nulls an empty datetime on every write) — both as ticket 56 decided them.
 * The difference is only ever visible before the first save, and every input in
 * the stack binds these two the same way either way.
 */
function emptyValue(field: FieldNode): any {
  if (field.fieldtype === "Check") return false;
  if (COLLECTIONS.has(field.fieldtype)) return [];
  if (NUMBERS.has(field.fieldtype)) return 0;
  return "";
}

/** A Select with no default lands on its first option, as desk does. */
function firstOption(field: FieldNode): string | undefined {
  if (field.fieldtype !== "Select") return undefined;
  const options = typeof field.options === "string" ? field.options : "";
  return options.split("\n")[0] || undefined;
}

function today(): string {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  const day = `${now.getDate()}`.padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}
