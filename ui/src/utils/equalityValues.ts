// The values a new record starts with from the filters it was created under.

const TABLE_TYPES = new Set(["Table", "Table MultiSelect"]);

/** The equality conditions on the doctype's own fields; a boolean is 1 or 0 for a Check, else Yes or No. */
export function equalityValues(
  conditions: [fieldname: string, operator: string, value: unknown][],
  fields: { fieldname: string; fieldtype: string }[]
): Record<string, unknown> {
  const own = new Map(
    fields
      .filter((field) => !TABLE_TYPES.has(field.fieldtype))
      .map((field) => [field.fieldname, field])
  );
  const values: Record<string, unknown> = {};
  for (const [fieldname, operator, value] of conditions) {
    const field = own.get(fieldname);
    if (operator !== "=" || !field) continue;
    values[fieldname] = typeof value === "boolean" ? fromBoolean(field.fieldtype, value) : value;
  }
  return values;
}

// The wire reads a "Yes" or "No" as a boolean whatever the field type.
function fromBoolean(fieldtype: string, value: boolean): number | string {
  if (fieldtype === "Check") return Number(value);
  return value ? "Yes" : "No";
}
