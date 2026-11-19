// What each piece of a `depends_on` condition means as a builder row. The
// grammar is `dependsOnReader`; a form whose meaning a row would change throws.
import { isOptionField } from "../../Filter/operators";
import type {
  ConditionField,
  ConditionNode,
  ConditionOperator,
  ConditionValue,
  DependsOnScope,
  FieldConditionValue,
} from "../types";
import { NUMERIC_FIELDTYPES } from "./operators";

type Leaf = FieldConditionValue;
type Literal = string | number | boolean | null;

export type Operand =
  | { kind: "field"; name: string; length: boolean }
  | { kind: "literal"; value: Literal }
  | { kind: "list"; items: (string | number)[] }
  | { kind: "indexOf"; items: (string | number)[]; name: string }
  | { kind: "row"; leaf: Leaf };

export const RECORD_IS_NEW = "__islocal";
export const DOCUMENT_STATUS = "docstatus";
/** `doc.docstatus` 0, 1 and 2, by index. Values, not labels: never translated. */
export const DOCUMENT_STATUSES = ["Draft", "Submitted", "Cancelled"];
/** A value naming a field of the same record rather than a fixed value. */
export const FIELD_REFERENCE = "eval:";
/** Numbers in the document, so their literals are written unquoted. */
export const NUMBER_FIELDTYPES = [...NUMERIC_FIELDTYPES, "Duration"];

const EQUAL = ["==", "==="];
/** `==` and `!=` convert, so they hold for values a row tells apart. */
const LOOSE = ["==", "!="];
/** `===` and `!==` never convert, so their value must already be the field's type. */
const STRICT = ["===", "!=="];
const UNEQUAL = ["!=", "!=="];
const ORDERING = ["<", ">", "<=", ">="];
const MIRROR: Record<string, string> = {
  "<": ">",
  ">": "<",
  "<=": ">=",
  ">=": "<=",
};
const OPPOSITE: Partial<Record<ConditionOperator, ConditionOperator>> = {
  equals: "not equals",
  "not equals": "equals",
  in: "not in",
  "not in": "in",
  like: "not like",
  "not like": "like",
};

export class DependsOnRules {
  constructor(private scope: DependsOnScope) {}

  /** `doc.x`, or `doc.x.length` when `x` is a table. */
  fieldOperand(name: string, length: boolean): Operand {
    // `doc.items` is an array, true even with no rows; only `.length` asks.
    if (this.scope.tables.has(name) !== length) {
      throw new SyntaxError("A table is read by its length");
    }
    return { kind: "field", name, length };
  }

  /** A field read on its own: `doc.customer`, `doc.is_pos`, `doc.items.length`. */
  truthy(operand: Operand): ConditionNode {
    if (operand.kind === "row") return operand.leaf;
    if (operand.kind !== "field")
      throw new SyntaxError("A value is not a condition");
    if (this.field(operand.name).fieldtype === "Check") {
      return row(operand.name, "equals", "Yes");
    }
    return row(operand.name, "is", "set");
  }

  compare(left: Operand, op: string, right: Operand): ConditionNode {
    if (left.kind === "literal" && right.kind === "field" && MIRROR[op]) {
      return this.compare(right, MIRROR[op], left);
    }
    if (left.kind === "indexOf" && right.kind === "literal") {
      return this.indexOf(left, op, right.value);
    }
    if (left.kind !== "field") throw new SyntaxError("Compare a field");
    if (left.length) return this.rowCount(left.name, op, right);
    if (right.kind === "field") return this.compareFields(left.name, op, right);
    if (right.kind !== "literal") throw new SyntaxError("Compare with a value");
    return this.compareValue(left.name, op, right.value);
  }

  /** `in_list([...], doc.x)` and `[...].includes(doc.x)`. */
  member(items: (string | number)[], operand: Operand): Leaf {
    if (operand.kind !== "field" || operand.length)
      throw new SyntaxError("Find a field");
    if (!items.length) throw new SyntaxError("An empty list is never matched");
    return row(operand.name, "in", this.listValue(operand.name, items));
  }

  /**
   * `(doc.x || "").includes("y")`, or `String(doc.x ?? "")` for a number:
   * `|| ""` turns 0 into no text, and leaves any other number without `includes`.
   */
  contains(operand: Operand, text: Literal, stringOf: boolean): Leaf {
    if (
      operand.kind !== "field" ||
      operand.length ||
      typeof text !== "string" ||
      text === "" ||
      text.startsWith(FIELD_REFERENCE)
    ) {
      throw new SyntaxError("A field contains text");
    }
    const field = this.field(operand.name);
    if (field.fieldtype === "Check" || operand.name === DOCUMENT_STATUS) {
      throw new SyntaxError("A Check or a status holds no text");
    }
    // The forms differ on a number, which a text field can hold after a fetch.
    if (NUMBER_FIELDTYPES.includes(field.fieldtype) !== stringOf) {
      throw new SyntaxError('A number is read with String, text with || ""');
    }
    return row(operand.name, "like", text);
  }

  /** `from <= x && x <= to`: an ordering, so text against a number converts. */
  between(operand: Operand, from: Literal, to: Literal): Leaf {
    if (operand.kind !== "field" || operand.length)
      throw new SyntaxError("Not a range");
    const field = this.field(operand.name);
    if (field.fieldtype === "Check" || operand.name === DOCUMENT_STATUS) {
      throw new SyntaxError("A Check or a status is not ordered");
    }
    const ends = [
      this.value(field, from, true, true),
      this.value(field, to, true, true),
    ];
    // A row drops an empty end as unfinished.
    if (ends.includes("")) throw new SyntaxError("A range has two ends");
    return row(operand.name, "between", ends as string[]);
  }

  /** `!x`. A negated group has no row of its own, and De Morgan would rewrite it. */
  negate(node: ConditionNode): ConditionNode {
    if ("conditions" in node) {
      if (node.conditions.length !== 1)
        throw new SyntaxError("A negated group stays code");
      return this.negate(node.conditions[0]);
    }
    const field = this.field(node.fieldname);
    if (
      field.fieldtype === "Check" &&
      node.operator === "equals" &&
      isYesNo(node.value)
    ) {
      return { ...node, value: node.value === "Yes" ? "No" : "Yes" };
    }
    if (node.operator === "is") {
      return { ...node, value: node.value === "set" ? "not set" : "set" };
    }
    // `!(a < 1)` is not `a >= 1` when `a` is empty.
    const operator = OPPOSITE[node.operator];
    if (!operator)
      throw new SyntaxError("Only an equality or a membership negates");
    return { ...node, operator };
  }

  field(name: string): ConditionField {
    const field = this.scope.fields.find((one) => one.fieldname === name);
    if (!field) throw new SyntaxError(`Unknown field ${name}`);
    return field;
  }

  private compareFields(
    name: string,
    op: string,
    right: Operand & { kind: "field" }
  ) {
    if (right.length || this.scope.tables.has(right.name)) {
      throw new SyntaxError("Compare with a field's value");
    }
    // A row compares two fields strictly: `5 == "5"` and `null == undefined` hold.
    if (LOOSE.includes(op))
      throw new SyntaxError("Compare two fields strictly");
    this.field(name);
    this.field(right.name);
    return row(name, this.operator(op), fieldReference(right.name));
  }

  private compareValue(name: string, op: string, value: Literal): Leaf {
    const field = this.field(name);
    const operator = this.operator(op);
    // `== null` and `== undefined` are true of neither "" nor 0: no row says that.
    if (value === null) throw new SyntaxError("Compare with a value");
    const loose = !STRICT.includes(op);
    if (field.fieldtype === "Check")
      return checkRow(name, operator, value, loose);
    if (name === DOCUMENT_STATUS) {
      if (ORDERING.includes(op))
        throw new SyntaxError("A status is not ordered");
      return row(name, operator, documentStatus(value, loose));
    }
    return row(name, operator, this.value(field, value, loose));
  }

  /** `doc.items.length > 0` and the like: has rows, or has none. */
  private rowCount(name: string, op: string, right: Operand): Leaf {
    const count = right.kind === "literal" ? right.value : undefined;
    const some =
      (op === ">" && count === 0) || (UNEQUAL.includes(op) && count === 0);
    const none =
      (EQUAL.includes(op) && count === 0) || (op === "<" && count === 1);
    if (!some && !none) {
      throw new SyntaxError("Count a table's rows against 0");
    }
    return row(name, "equals", some ? "Yes" : "No");
  }

  /** `[...].indexOf(doc.x) !== -1` is a membership; any other bound is code. */
  private indexOf(
    left: Operand & { kind: "indexOf" },
    op: string,
    bound: Literal
  ): Leaf {
    const found =
      (UNEQUAL.includes(op) && bound === -1) || (op === ">" && bound === -1);
    const missing = EQUAL.includes(op) && bound === -1;
    if (!found && !missing) throw new SyntaxError("Compare indexOf with -1");
    const leaf = this.member(left.items, {
      kind: "field",
      name: left.name,
      length: false,
    });
    return found ? leaf : { ...leaf, operator: "not in" };
  }

  private operator(op: string): ConditionOperator {
    if (EQUAL.includes(op)) return "equals";
    if (UNEQUAL.includes(op)) return "not equals";
    if (ORDERING.includes(op)) return op as ConditionOperator;
    throw new SyntaxError(`Unknown comparison ${op}`);
  }

  /**
   * A list as the field's `in` control holds it: picked values, or a comma
   * string. `includes` never converts, and the control drops an empty item and
   * splits and trims a comma string, so such an item stays code.
   */
  private listValue(name: string, items: (string | number)[]): ConditionValue {
    const field = this.field(name);
    if (name === DOCUMENT_STATUS)
      return items.map((item) => documentStatus(item, false));
    const values = items.map((item) =>
      String(this.value(field, item, false, true))
    );
    const options = isOptionField(field.fieldtype);
    const kept = (value: string) =>
      value !== "" &&
      (options || (!value.includes(",") && value.trim() === value));
    if (!values.every(kept)) throw new SyntaxError("A list item is lost");
    return options ? values : values.join(", ");
  }

  /**
   * A literal as the row's value. A number field takes a number, or under `==`
   * and an ordering the text JavaScript converts to one; any other field takes
   * text. A compared value never reads as a field reference; a list item or a
   * range end is always text, so it may.
   */
  private value(
    field: ConditionField,
    value: Literal,
    loose: boolean,
    item = false
  ): string | number {
    const isNumber = NUMBER_FIELDTYPES.includes(field.fieldtype);
    if (typeof value === "number" && isNumber) return value;
    if (
      typeof value !== "string" ||
      (!item && value.startsWith(FIELD_REFERENCE))
    ) {
      throw new SyntaxError("Compare with a value of the field's type");
    }
    if (!isNumber) return value;
    const number = Number(value);
    if (loose && value.trim() !== "" && Number.isFinite(number)) return number;
    throw new SyntaxError("A number field never equals text");
  }
}

/** The value a row holds to compare with the field `name` of the record or its parent. */
export function fieldReference(name: string): string {
  return `${FIELD_REFERENCE}${
    name.startsWith("parent.") ? name : `doc.${name}`
  }`;
}

/** The field a value names, or null for a fixed value. */
export function referencedField(value: unknown): string | null {
  if (typeof value !== "string" || !value.startsWith(FIELD_REFERENCE))
    return null;
  const path = value.slice(FIELD_REFERENCE.length);
  return path.startsWith("doc.") ? path.slice(4) : path;
}

function row(
  fieldname: string,
  operator: ConditionOperator,
  value: ConditionValue
): Leaf {
  return { fieldname, operator, value };
}

/**
 * A Check against 1; `==` also matches `true` and `"1"`. A new record leaves a
 * Check with no default unset, which `=== 0` does not match and "No" does, so
 * a comparison with 0 stays code.
 */
function checkRow(
  name: string,
  operator: ConditionOperator,
  value: string | number | boolean,
  loose: boolean
) {
  const on = value === 1 || (loose && (value === true || value === "1"));
  if (!on || (operator !== "equals" && operator !== "not equals")) {
    throw new SyntaxError("A Check is compared with 1");
  }
  return row(name, "equals", operator === "equals" ? "Yes" : "No");
}

function documentStatus(
  value: string | number | boolean,
  loose: boolean
): string {
  const text = loose && typeof value === "string" && /^[012]$/.test(value);
  const status =
    DOCUMENT_STATUSES[typeof value === "number" || text ? Number(value) : NaN];
  if (!status) throw new SyntaxError("docstatus is 0, 1 or 2");
  return status;
}

function isYesNo(value: unknown) {
  return value === "Yes" || value === "No";
}
