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
 * The operators a field offers: each fieldtype maps to one operator set, and
 * the `_assign` field overrides to like/not like/is regardless of type.
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

/** The operator a freshly-added condition starts on, by fieldtype. */
export function getDefaultOperator(fieldtype: string): FilterOperator {
  if (SELECT_TYPES.includes(fieldtype)) return "equals";
  if (CHECK_TYPES.includes(fieldtype) || NUMBER_TYPES.includes(fieldtype))
    return "equals";
  if (DATE_TYPES.includes(fieldtype)) return "between";
  return "like";
}

/** The value a freshly-added condition starts with: Select seeds to its first
 *  option, Check to `Yes`, Date to null, everything else to an empty string. */
export function getDefaultValue(field: FilterField): FilterValue | null {
  if (SELECT_TYPES.includes(field.fieldtype)) {
    return (field.options ?? "").split("\n")[0];
  }
  if (CHECK_TYPES.includes(field.fieldtype)) return "Yes";
  if (DATE_TYPES.includes(field.fieldtype)) return null;
  return "";
}

/**
 * Whether `in`/`not in` over this fieldtype picks from a known option set — a
 * MultiSelect holding a `string[]` rather than a comma-separated text box.
 * Dynamic Link has no fixed target, so it stays on the comma TextInput.
 */
export function isOptionField(fieldtype: string): boolean {
  return (
    SELECT_TYPES.includes(fieldtype) ||
    (LINK_TYPES.includes(fieldtype) && fieldtype !== "Dynamic Link")
  );
}

/**
 * The value a condition resets to for a given operator on a field. `is`/`is not`
 * seed to `set`; `in`/`not in` to an empty list on an option field or an empty
 * comma box otherwise; everything else to the field's by-type default.
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
// A row keeps its operator and value where they still make sense for the new
// field, so refining "Status equals Open" into "Priority equals …" doesn't drop
// the "equals".

/**
 * Operators whose value carries verbatim because it isn't bound to the field's
 * option set. `in`/`not in` are excluded: their value is a list tied to one
 * field, so it carries only where {@link valueCarries} finds a shared domain.
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
  // A condition whose own field is gone has no domain to compare. Keep the
  // stored value unless the new field's own option list proves it cannot hold it.
  if (!prev.field) {
    if (SELECT_TYPES.includes(field.fieldtype)) {
      return (field.options ?? "").split("\n").includes(prev.value as string);
    }
    if (CHECK_TYPES.includes(field.fieldtype)) {
      return prev.value === "Yes" || prev.value === "No";
    }
    // What a deleted field left behind is text, so only a text field can still
    // hold it. Carrying it further hands a Date, number, Link, Duration or
    // Rating control a word it cannot render or compare.
    return valueDomain(field.fieldtype) === "text";
  }
  if (valueDomain(prev.field.fieldtype) !== valueDomain(field.fieldtype)) {
    return false;
  }
  // Select values must exist in the new field's options; Link values belong to
  // one target doctype — both can mismatch even within the same domain.
  if (SELECT_TYPES.includes(field.fieldtype)) {
    return (field.options ?? "").split("\n").includes(prev.value as string);
  }
  if (LINK_TYPES.includes(field.fieldtype))
    return prev.field.options === field.options;
  return true;
}

/**
 * The next condition when a row's field changes. Keeps the operator if the new
 * field offers it (else the field's default), then keeps the value when it still
 * applies — operator-driven, or the two fields share a value domain.
 */
export function carryOver(
  prev: Filter,
  field: FilterField,
  // What the new field is actually offered, for a caller whose vocabulary is not
  // this module's: `ConditionBuilder` adds `is not` and withholds `timespan`, and
  // checking against `getOperators` would read its own operators as unavailable
  // and reset the row on every field change.
  offered: OperatorOption[] = getOperators(field.fieldtype, field.fieldname)
): Filter {
  const keepOperator = offered.some((o) => o.value === prev.operator);
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
