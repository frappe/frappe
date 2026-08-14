// What a freshly added child row starts with, from its docfield defaults.
import type { FieldNode, FormLayoutSchema } from "./types";

const NO_VALUE = new Set([
  "Section Break",
  "Column Break",
  "Tab Break",
  "Heading",
  "HTML",
  "Fold",
]);

const INTEGERS = new Set(["Int", "Check"]);
const DECIMALS = new Set(["Float", "Currency", "Percent"]);

/**
 * Seed values for a new row: every field's resolved `default`, plus a Select's
 * first option, which Frappe treats as the default when none is declared.
 */
export function newRowValues(fields: FieldNode[]): Record<string, any> {
  const row: Record<string, any> = {};
  for (const field of fields) {
    if (NO_VALUE.has(field.fieldtype)) continue;
    const value = defaultValue(field);
    if (value !== undefined) row[field.fieldname] = value;
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
  if (raw == null || raw === "") return firstOption(field);
  if (raw === "Today" || raw === "today") return today();
  if (raw === "Now" || raw === "now") return new Date().toISOString().slice(0, 19).replace("T", " ");
  if (INTEGERS.has(field.fieldtype)) return Math.trunc(Number(raw)) || 0;
  if (DECIMALS.has(field.fieldtype)) return Number(raw) || 0;
  return raw;
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
