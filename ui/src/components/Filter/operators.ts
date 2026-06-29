import type { FilterField, FilterOperator, FilterValue } from "./types";

/** An operator choice offered for a field, ready for a Select control. */
export interface OperatorOption {
  label: string;
  value: FilterOperator;
}

const STRING_TYPES = ["Data", "Long Text", "Small Text", "Text Editor", "Text"];
const NUMBER_TYPES = ["Float", "Int", "Currency", "Percent"];
const SELECT_TYPES = ["Select"];
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
