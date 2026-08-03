import type { Filter, FilterField, FilterOperator, FilterValue } from "./types";

/** One Frappe wire condition: a `[fieldname, operator, value]` triple. */
export type WireFilter = [string, string, unknown];

/** The Frappe wire form of a list's narrowing: a list of `[fieldname, operator,
 *  value]` conditions. A list (not a fieldname-keyed dict) so the same field can
 *  carry more than one condition — e.g. `amount > 100 AND amount < 500`. The
 *  serialized form of a list of Filters. */
export type WireFilters = WireFilter[];

/** Maps a Filter's UI operator to its Frappe wire operator. Ported from CRM's
 *  `operatorMap`. */
const WIRE_OPERATOR: Record<FilterOperator, string> = {
  is: "is",
  "is not": "is not",
  in: "in",
  "not in": "not in",
  equals: "=",
  "not equals": "!=",
  like: "LIKE",
  "not like": "NOT LIKE",
  ">": ">",
  "<": "<",
  ">=": ">=",
  "<=": "<=",
  between: "between",
  timespan: "timespan",
};

/** Coerce a condition's value into its wire shape. Ported from CRM's
 *  `transformIn`: `like` operators get `%`-wrapped. */
function toWireValue(operator: FilterOperator, value: FilterValue): unknown {
  if (
    operator.includes("like") &&
    typeof value === "string" &&
    !value.includes("%")
  ) {
    return `%${value}%`;
  }
  if (operator === "in" || operator === "not in") {
    // Option fields supply a ready array (MultiSelect); free-text fields a
    // comma string to split.
    if (Array.isArray(value)) return value;
    if (typeof value === "string")
      return value
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
  }
  return value;
}

/** Maps a Frappe wire operator back to a Filter's UI operator. The inverse of
 *  {@link WIRE_OPERATOR}; ported from CRM's `oppositeOperatorMap`. */
const UI_OPERATOR: Record<string, FilterOperator> = {
  is: "is",
  "is not": "is not",
  in: "in",
  "not in": "not in",
  "=": "equals",
  "!=": "not equals",
  equals: "equals",
  LIKE: "like",
  "NOT LIKE": "not like",
  ">": ">",
  "<": "<",
  ">=": ">=",
  "<=": "<=",
  between: "between",
  timespan: "timespan",
};

/**
 * Parse a Frappe wire filter list back into a list of Filters, the inverse of
 * {@link serializeFilters}. A `[fieldname, operator, value]` triple maps the
 * wire operator back to its UI form (a Check field's `=`-boolean surfaces as a
 * `Yes`/`No` equals). Conditions whose field is absent from `fields` are dropped
 * (the control can't render a row without Meta). Order is preserved, so two
 * conditions on the same field round-trip as two rows.
 */
export function parseFilters(
  fields: FilterField[],
  wire: WireFilters
): Filter[] {
  const byName = new Map(fields.map((f) => [f.fieldname, f]));
  const conditions: Filter[] = [];
  for (const [fieldname, wireOperator, raw] of wire) {
    const field = byName.get(fieldname);
    if (!field) continue;
    let operator: FilterOperator;
    let value: FilterValue;
    if (field.fieldtype === "Check" && typeof raw === "boolean") {
      operator = "equals";
      value = raw ? "Yes" : "No";
    } else {
      operator = UI_OPERATOR[wireOperator];
      value = raw as FilterValue;
    }
    conditions.push({ field, fieldname, operator, value });
  }
  return conditions;
}

/**
 * Serialize a list of Filters into the Frappe wire filter list. Each condition
 * becomes a `[fieldname, wireOperator, value]` triple (an `equals` uses `=`; a
 * Check `Yes`/`No` becomes a boolean). The list form — rather than CRM's
 * fieldname-keyed dict — lets the same field appear in more than one condition.
 */
export function serializeFilters(conditions: Filter[]): WireFilters {
  return conditions.map((c) => {
    if (c.operator === "equals") {
      const value =
        c.value === "Yes" ? true : c.value === "No" ? false : c.value;
      return [c.fieldname, "=", value];
    }
    return [
      c.fieldname,
      WIRE_OPERATOR[c.operator],
      toWireValue(c.operator, c.value),
    ];
  });
}
