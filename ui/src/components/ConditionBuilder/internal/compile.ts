// Compiling the interleaved array into the Python expression `safe_eval` runs.
//
// `foldEntries` sits here rather than beside the parser because both readers of
// the array need it and this is the lower of the two: `adapters.ts` imports it,
// nothing here imports `adapters.ts`.
import type {
  ConditionExpressionOptions,
  ConditionOperator,
  Conjunction,
} from "../types";
import {
  NUMERIC_FIELDTYPES,
  OPERATORS,
  ORDERING,
  SCALAR_COMPARISONS,
  pythonToken,
} from "./operators";

/**
 * Split one level into operands and separators. An entry `read` makes nothing
 * of takes its pending separator with it. Every separator is returned: only
 * `fromFrappeConditions` collapses them.
 */
export function foldEntries<T>(
  entries: unknown[],
  read: (entry: unknown) => T | null
): { items: T[]; separators: Conjunction[] } {
  const items: T[] = [];
  const separators: Conjunction[] = [];
  let pending: Conjunction | null = null;

  for (const entry of entries) {
    const token = asConjunction(entry);
    if (token !== null) {
      pending = token;
      continue;
    }

    const item = read(entry);
    if (item === null) {
      pending = null;
      continue;
    }

    if (items.length > 0) separators.push(pending ?? "and");
    items.push(item);
    pending = null;
  }

  return { items, separators };
}

/** The separator tokens, case-insensitively: a hand-edited record can carry
 *  `"OR"`, and sending it down the operand path would invert the rule. */
function asConjunction(item: unknown): Conjunction | null {
  if (typeof item !== "string") return null;
  const token = item.trim().toLowerCase();
  return token === "and" || token === "or" ? token : null;
}

/** One level of the array, as the expression it evaluates to. */
export function compileEntries(
  entries: unknown[],
  options: ConditionExpressionOptions
): string {
  const { items, separators } = foldEntries(entries, (entry) => {
    const compiled = compileEntry(entry, options);
    return compiled === "" ? null : compiled;
  });

  return items.reduce(
    (expression, operand, index) =>
      index === 0
        ? operand
        : `${expression} ${separators[index - 1]} ${operand}`,
    ""
  );
}

/** A nested group is parenthesised, so the tree's shape decides the reading
 *  rather than Python's precedence. */
function compileEntry(
  entry: unknown,
  options: ConditionExpressionOptions
): string {
  if (Array.isArray(entry) && Array.isArray(entry[0])) {
    const nested = compileEntries(entry, options);
    return nested === "" ? "" : `(${nested})`;
  }
  return compileLeaf(entry, options);
}

function compileLeaf(
  entry: unknown,
  options: ConditionExpressionOptions
): string {
  if (
    !Array.isArray(entry) ||
    entry.length !== 3 ||
    typeof entry[0] !== "string"
  ) {
    return "";
  }

  const [fieldname, rawOperator, value] = entry;
  const { fieldPrefix, fields } = options;
  const field = fieldPrefix ? `${fieldPrefix}.${fieldname}` : fieldname;
  const token = String(rawOperator).toLowerCase();
  const rule = Object.hasOwn(OPERATORS, token)
    ? OPERATORS[token as ConditionOperator]
    : undefined;
  const operator = rule ? pythonToken(token, rule) : token;
  const fieldtype = fields?.find((f) => f.fieldname === fieldname)?.fieldtype;

  // A Check holds "Yes"/"No" but the document holds 0/1, which `== "Yes"` never
  // matches. Without `fields` the value is all there is to go on.
  const check = String(value).trim().toLowerCase();
  const isCheck =
    fields !== undefined
      ? fieldtype === "Check"
      : check === "yes" || check === "no";
  if (
    (operator === "==" || operator === "!=") &&
    isCheck &&
    (check === "yes" || check === "no")
  ) {
    return (check === "yes") === (operator === "==") ? field : `not ${field}`;
  }

  // All four pairings of is/is not against Set/Not Set are the field's own
  // truthiness.
  if (operator === "is" || operator === "is not") {
    if (check === "set" || check === "not set") {
      return (check === "set") === (operator === "is") ? field : `not ${field}`;
    }
  }

  const isNumeric =
    fieldtype !== undefined && NUMERIC_FIELDTYPES.includes(fieldtype);

  // `field and` keeps a null out of the membership test, where it would raise.
  // A number cannot be its subject at all and `safe_eval` has no `str` to
  // coerce with.
  if (operator === "like" || operator === "not like") {
    if (isNumeric) return "";
    // `"" in doc.subject` is True of every document that has one, so `like ""`
    // would read as "is set". This is where a fresh text row starts.
    if (!isNamed(value)) return "";
    const membership = operator === "like" ? "in" : "not in";
    return `(${field} and ${quote(value)} ${membership} ${field})`;
  }

  // A numeric member goes in unquoted or it matches nothing: `100 in ["100"]`
  // is False.
  if (operator === "in" || operator === "not in") {
    // `in []` matches nothing and `not in []` matches everything, so an
    // unfinished row would fire on all of them.
    const members = asList(value).filter(isNamed);
    if (members.length === 0) return "";
    const items = members.map((item) => literal(item, isNumeric)).join(", ");
    return `(${field} and ${field} ${operator} [${items}])`;
  }

  // `between` answers for itself rather than falling through to the unset-value
  // rule below, which would turn a cleared range into "is set".
  if (operator === "between") {
    const range = asRange(value);
    if (!range) return "";
    const from = rangeEnd(range[0], isNumeric);
    const to = rangeEnd(range[1], isNumeric);
    return from !== null && to !== null
      ? `(${field} >= ${from} and ${field} <= ${to})`
      : "";
  }

  // An unset value is the field's own falsiness. `field == None` is not what an
  // empty condition means.
  if (value === null || value === undefined) {
    return operator === "==" || operator === "is" ? `not ${field}` : field;
  }

  if (!SCALAR_COMPARISONS.includes(operator)) return "";

  // `doc.grand_total > "100"` is a TypeError, not False. An unreadable value
  // drops the row where the comparison is an ordering; `==`/`!=` compile quoted.
  if (isNumeric) {
    const number = numeric(value);
    if (number !== null) return `${field} ${operator} ${number}`;
    if (ORDERING.includes(operator)) return "";
  }

  if (typeof value === "number") return `${field} ${operator} ${value}`;
  // Python's booleans: `true` is a NameError under `safe_eval`.
  if (typeof value === "boolean")
    return `${field} ${operator} ${value ? "True" : "False"}`;

  return `${field} ${operator} ${quote(value)}`;
}

const CONTROL = /[\u0000-\u001f\u007f]/g;
const NAMED_ESCAPE: Record<string, string> = {
  "\n": "\\n",
  "\r": "\\r",
  "\t": "\\t",
};

/**
 * A Python string literal. The backslash goes first, or it escapes the escapes.
 * A raw newline would end the literal, and an unparseable rule matches nothing.
 */
function quote(value: unknown): string {
  const escaped = String(value)
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(
      CONTROL,
      (character) =>
        NAMED_ESCAPE[character] ??
        `\\x${character.charCodeAt(0).toString(16).padStart(2, "0")}`
    );
  return `"${escaped}"`;
}

/** A value as a Python number, or null where it cannot be read as one. */
function numeric(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const text = String(value).trim();
  if (text === "") return null;
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}

/** A list member, as the literal it compiles to. */
function literal(value: unknown, isNumeric: boolean): string {
  if (isNumeric) {
    const number = numeric(value);
    if (number !== null) return String(number);
  }
  return quote(value);
}

/** One end of a range, or null where an ordering comparison could not use it. */
function rangeEnd(value: unknown, isNumeric: boolean): string | null {
  if (!isNumeric) return quote(value);
  const number = numeric(value);
  return number === null ? null : String(number);
}

/** `in`'s operand: a list as it stands, a comma string as its parts. */
function asList(value: unknown): unknown[] {
  if (Array.isArray(value)) return value.map((item) => String(item).trim());
  if (typeof value === "string")
    return value.split(",").map((item) => item.trim());
  return [value];
}

/** `between`'s two ends, or null unless both are named: a cleared picker leaves
 *  `[null, null]`, and `>= ""` is true of every date there is. */
function asRange(value: unknown): [unknown, unknown] | null {
  const pair = asPair(value);
  return pair !== null && pair.every(isNamed) ? pair : null;
}

function asPair(value: unknown): [unknown, unknown] | null {
  if (Array.isArray(value))
    return value.length === 2 ? [value[0], value[1]] : null;
  if (typeof value !== "string" || !value.includes(",")) return null;
  const [from, to] = value.split(",").map((part) => part.trim());
  return [from, to];
}

function isNamed(end: unknown): boolean {
  return end !== null && end !== undefined && String(end).trim() !== "";
}
