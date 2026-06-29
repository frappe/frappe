import type { Filter, FilterField, FilterOperator, FilterValue } from "./types";

/** The Frappe wire form of a list's narrowing: a map of fieldname to either a
 *  bare value (`equals`) or an `[operator, value]` pair. The serialized form of
 *  a list of Filters. */
export type FiltersDict = Record<string, unknown>;

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
  if (
    (operator === "in" || operator === "not in") &&
    typeof value === "string"
  ) {
    return value.split(",").map((v) => v.trim());
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
 * Parse a Frappe wire dict back into a list of Filters, the inverse of
 * {@link serializeFilters}. A port of CRM's `convertFilters`: a bare value
 * becomes an `equals` condition (Check booleans surface as `Yes`/`No`), an
 * `[operator, value]` pair maps the operator back to its UI form. Fields absent
 * from `fields` are dropped (the control can't render a row without Meta).
 */
export function parseFilters(
  fields: FilterField[],
  wire: FiltersDict
): Filter[] {
  const byName = new Map(fields.map((f) => [f.fieldname, f]));
  const conditions: Filter[] = [];
  for (const [fieldname, raw] of Object.entries(wire)) {
    const field = byName.get(fieldname);
    if (!field) continue;
    let pair: [string, unknown];
    if (Array.isArray(raw)) {
      pair = [raw[0], raw[1]];
    } else if (field.fieldtype === "Check") {
      pair = ["equals", raw ? "Yes" : "No"];
    } else {
      pair = ["=", raw];
    }
    conditions.push({
      field,
      fieldname,
      operator: UI_OPERATOR[pair[0]],
      value: pair[1] as FilterValue,
    });
  }
  return conditions;
}

/**
 * Serialize a list of Filters into the Frappe wire dict. A port of CRM's
 * `parseFilters` + `transformIn`: an `equals` condition collapses to a bare
 * value; every other operator becomes an `[wireOperator, value]` pair.
 */
export function serializeFilters(conditions: Filter[]): FiltersDict {
  const out: FiltersDict = {};
  for (const c of conditions) {
    if (c.operator === "equals") {
      out[c.fieldname] =
        c.value === "Yes" ? true : c.value === "No" ? false : c.value;
    } else {
      out[c.fieldname] = [
        WIRE_OPERATOR[c.operator],
        toWireValue(c.operator, c.value),
      ];
    }
  }
  return out;
}
