import type { Filter, FilterField, FilterOperator, FilterValue } from "./types";

/** An operator choice offered for a field, ready for a Select control. */
export interface OperatorOption {
  label: string;
  value: FilterOperator;
}

const STRING_TYPES = ["Data", "Long Text", "Small Text", "Text Editor", "Text"];
const NUMBER_TYPES = ["Float", "Int", "Currency", "Percent"];
// `Autocomplete` carries a newline option list like `Select` and filters the same
// way, so it shares the Select operator set, defaults, and value inputs.
const SELECT_TYPES = ["Select", "Autocomplete"];
const LINK_TYPES = ["Link", "Dynamic Link"];
const CHECK_TYPES = ["Check"];
const DURATION_TYPES = ["Duration"];
const DATE_TYPES = ["Date", "Datetime"];
const RATING_TYPES = ["Rating"];

const op = (value: FilterOperator, label: string): OperatorOption => ({
  label,
  value,
});

const EQUALS = op("equals", "Equals");
const NOT_EQUALS = op("not equals", "Not equals");
const LIKE = op("like", "Like");
const NOT_LIKE = op("not like", "Not like");
const IN = op("in", "In");
const NOT_IN = op("not in", "Not in");
const IS = op("is", "Is");

const STRING_OPERATORS = [EQUALS, NOT_EQUALS, LIKE, NOT_LIKE, IN, NOT_IN, IS];
const NUMBER_OPERATORS = [
  EQUALS,
  NOT_EQUALS,
  LIKE,
  NOT_LIKE,
  IN,
  NOT_IN,
  IS,
  op("<", "<"),
  op(">", ">"),
  op("<=", "<="),
  op(">=", ">="),
];
const SELECT_OPERATORS = [EQUALS, NOT_EQUALS, IN, NOT_IN, IS];
const LINK_OPERATORS = [EQUALS, NOT_EQUALS, LIKE, NOT_LIKE, IN, NOT_IN, IS];
const CHECK_OPERATORS = [EQUALS];
const DURATION_OPERATORS = [LIKE, NOT_LIKE, IN, NOT_IN, IS];
const DATE_OPERATORS = [
  EQUALS,
  NOT_EQUALS,
  IS,
  op(">", ">"),
  op("<", "<"),
  op(">=", ">="),
  op("<=", "<="),
  op("between", "Between"),
  op("timespan", "Timespan"),
];
const RATING_OPERATORS = [
  EQUALS,
  NOT_EQUALS,
  op(">", "Greater than"),
  op("<", "Less than"),
  op(">=", "Greater than or equal to"),
  op("<=", "Less than or equal to"),
  IS,
];
const ASSIGN_OPERATORS = [LIKE, NOT_LIKE, IS];

/**
 * The operators a field offers, by fieldtype (with field-name special cases).
 * A pure port of CRM's `getOperators`: each fieldtype maps to one operator set,
 * and the `_assign` field overrides to like/not like/is regardless of type.
 */
export function getOperators(
  fieldtype: string,
  fieldname = ""
): OperatorOption[] {
  if (fieldname === "_assign") return [...ASSIGN_OPERATORS];
  if (STRING_TYPES.includes(fieldtype)) return [...STRING_OPERATORS];
  if (NUMBER_TYPES.includes(fieldtype)) return [...NUMBER_OPERATORS];
  if (SELECT_TYPES.includes(fieldtype)) return [...SELECT_OPERATORS];
  if (LINK_TYPES.includes(fieldtype)) return [...LINK_OPERATORS];
  if (CHECK_TYPES.includes(fieldtype)) return [...CHECK_OPERATORS];
  if (DURATION_TYPES.includes(fieldtype)) return [...DURATION_OPERATORS];
  if (DATE_TYPES.includes(fieldtype)) return [...DATE_OPERATORS];
  if (RATING_TYPES.includes(fieldtype)) return [...RATING_OPERATORS];
  return [];
}

/** The operator a freshly-added condition starts on, by fieldtype. Ported from
 *  CRM's `getDefaultOperator`. */
export function getDefaultOperator(fieldtype: string): FilterOperator {
  if (SELECT_TYPES.includes(fieldtype)) return "equals";
  if (CHECK_TYPES.includes(fieldtype) || NUMBER_TYPES.includes(fieldtype))
    return "equals";
  if (DATE_TYPES.includes(fieldtype)) return "between";
  return "like";
}

/** The value a freshly-added condition starts with, by field. Ported from CRM's
 *  `getDefaultValue`: Select seeds to its first option, Check to `Yes`, Date to
 *  an empty (null) value, everything else to an empty string. */
export function getDefaultValue(field: FilterField): FilterValue | null {
  if (SELECT_TYPES.includes(field.fieldtype)) {
    return (field.options ?? "").split("\n")[0];
  }
  if (CHECK_TYPES.includes(field.fieldtype)) return "Yes";
  if (DATE_TYPES.includes(field.fieldtype)) return null;
  return "";
}

/**
 * Whether `in`/`not in` over this fieldtype picks from a known option set — so the
 * value control is a MultiSelect (and the value a `string[]`) instead of a free,
 * comma-separated text box. Select/Autocomplete carry their options inline; a Link
 * resolves them from its target doctype. Dynamic Link has no fixed target, so it
 * (and every free-text/number fieldtype) stays on the comma TextInput.
 */
export function isOptionField(fieldtype: string): boolean {
  return (
    SELECT_TYPES.includes(fieldtype) ||
    (LINK_TYPES.includes(fieldtype) && fieldtype !== "Dynamic Link")
  );
}

/**
 * The value a condition resets to for a given operator on a field. `is`/`is not`
 * seed to `set`; `in`/`not in` seed to an empty multi-select list (`[]`) on an
 * option field or an empty comma box (`''`) otherwise; everything else falls back
 * to the field's by-type default. Used when an operator change or a field change
 * invalidates the previous value.
 */
export function defaultValueFor(
  field: FilterField,
  operator: FilterOperator
): FilterValue {
  if (operator === "is" || operator === "is not") return "set";
  if (operator === "in" || operator === "not in") {
    return isOptionField(field.fieldtype) ? [] : "";
  }
  return getDefaultValue(field) as FilterValue;
}

/** A fresh condition seeded with the field's default operator and value. */
export function conditionFor(field: FilterField): Filter {
  return {
    field,
    fieldname: field.fieldname,
    operator: getDefaultOperator(field.fieldtype),
    value: getDefaultValue(field) as FilterValue,
  };
}

// --- Field-change carry-over -------------------------------------------------
// When a row's field changes we keep its operator (and value) where they still
// make sense for the new field, instead of snapping back to the fieldtype
// defaults — so refining "Status equals Open" into "Priority equals …" doesn't
// drop the "equals". A UX nicety over CRM, which always resets on field change.

/**
 * Operators whose value carries verbatim across a field change because it isn't
 * bound to the field's option set: `like`/`not like` are free text. `in`/`not in`
 * are deliberately excluded — their value is an option list tied to one field (a
 * `string[]` on option fields), so it resets via {@link defaultValueFor} unless
 * {@link valueCarries} finds the new field shares the domain (e.g. two `User`
 * Links keep their picks).
 */
const CARRYING_OPERATORS: FilterOperator[] = ["like", "not like"];

/** The value-input "domain" a fieldtype maps to. A condition's value only carries
 *  between two fields of the same domain (a number means nothing in a date input). */
function valueDomain(fieldtype: string): string {
  if (NUMBER_TYPES.includes(fieldtype)) return "number";
  if (DATE_TYPES.includes(fieldtype)) return "date";
  if (SELECT_TYPES.includes(fieldtype)) return "select";
  if (CHECK_TYPES.includes(fieldtype)) return "check";
  if (LINK_TYPES.includes(fieldtype)) return "link";
  if (DURATION_TYPES.includes(fieldtype)) return "duration";
  if (RATING_TYPES.includes(fieldtype)) return "rating";
  return "text";
}

/** Whether `prev`'s value still applies to `field`, given a kept operator. */
function valueCarries(prev: Filter, field: FilterField): boolean {
  if (prev.value === "" || prev.value == null) return false;
  if (
    valueDomain(prev.field?.fieldtype ?? "Data") !==
    valueDomain(field.fieldtype)
  ) {
    return false;
  }
  // Select values must exist in the new field's options; Link values belong to
  // one target doctype — both can mismatch even within the same domain.
  if (SELECT_TYPES.includes(field.fieldtype)) {
    return (field.options ?? "").split("\n").includes(prev.value as string);
  }
  if (LINK_TYPES.includes(field.fieldtype))
    return prev.field?.options === field.options;
  return true;
}

/**
 * The next condition when a row's field changes. Keeps the operator if the new
 * field still offers it (else the field's default), then keeps the value when it
 * still applies — operator-driven (set/not-set or free text), or the new field
 * shares the old one's value domain (with Select options / Link doctype matched).
 */
export function carryOver(prev: Filter, field: FilterField): Filter {
  const keepOperator = getOperators(field.fieldtype, field.fieldname).some(
    (o) => o.value === prev.operator
  );
  if (!keepOperator) return conditionFor(field);

  const operator = prev.operator;
  const operatorDriven =
    operator === "is" ||
    operator === "is not" ||
    CARRYING_OPERATORS.includes(operator);
  const value = (
    operatorDriven || valueCarries(prev, field)
      ? prev.value
      : defaultValueFor(field, operator)
  ) as FilterValue;
  return { field, fieldname: field.fieldname, operator, value };
}
