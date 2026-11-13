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

  /** A field read on its own: `doc.customer`, `doc.is_pos`, `doc.items.length`. */
  truthy(operand: Operand): ConditionNode {
    if (operand.kind === "row") return operand.leaf;
    if (operand.kind !== "field")
      throw new SyntaxError("A value is not a condition");
    // `doc.items` is an array, true even with no rows; only `.length` asks.
    if (this.scope.tables.has(operand.name) !== operand.length) {
      throw new SyntaxError("A table is read by its length");
    }
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

  /** `doc.x.includes("y")`. */
  contains(operand: Operand, text: Literal): Leaf {
    if (
      operand.kind !== "field" ||
      operand.length ||
      typeof text !== "string"
    ) {
      throw new SyntaxError("A field contains text");
    }
    this.field(operand.name);
    return row(operand.name, "like", text);
  }

  between(name: string, from: Literal, to: Literal): Leaf {
    const field = this.field(name);
    return row(name, "between", [
      this.value(field, from),
      this.value(field, to),
    ] as string[]);
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
    this.field(name);
    this.field(right.name);
    return row(name, this.operator(op), fieldReference(right.name));
  }

  private compareValue(name: string, op: string, value: Literal): Leaf {
    const field = this.field(name);
    const operator = this.operator(op);
    // `== null` and `== undefined` are true of neither "" nor 0: no row says that.
    if (value === null) throw new SyntaxError("Compare with a value");
    if (field.fieldtype === "Check") return checkRow(name, operator, value);
    if (typeof value === "boolean")
      throw new SyntaxError("Only a Check is true or false");
    if (name === DOCUMENT_STATUS) {
      if (ORDERING.includes(op))
        throw new SyntaxError("A status is not ordered");
      return row(name, operator, documentStatus(value));
    }
    return row(name, operator, this.value(field, value));
  }

  /** `doc.items.length > 0` and the like: has rows, or has none. */
  private rowCount(name: string, op: string, right: Operand): Leaf {
    const count = right.kind === "literal" ? right.value : undefined;
    const some =
      (op === ">" && count === 0) || (UNEQUAL.includes(op) && count === 0);
    const none =
      (EQUAL.includes(op) && count === 0) || (op === "<" && count === 1);
    if (!this.scope.tables.has(name) || (!some && !none)) {
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

  /** A list as the field's `in` control holds it: picked values, or a comma string. */
  private listValue(name: string, items: (string | number)[]): ConditionValue {
    const field = this.field(name);
    if (name === DOCUMENT_STATUS) return items.map(documentStatus);
    const values = items.map((item) => String(this.value(field, item)));
    return isOptionField(field.fieldtype) ? values : values.join(", ");
  }

  private value(field: ConditionField, value: Literal): string | number {
    if (typeof value === "boolean" || value === null) {
      throw new SyntaxError("Compare with text or a number");
    }
    const number = Number(value);
    if (
      NUMBER_FIELDTYPES.includes(field.fieldtype) &&
      value !== "" &&
      Number.isFinite(number)
    ) {
      return number;
    }
    return String(value);
  }
}

/** The value a row holds to mean "this record's `name`". */
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

function checkRow(
  name: string,
  operator: ConditionOperator,
  value: string | number | boolean
) {
  const on = value === 1 || value === true || value === "1";
  const off = value === 0 || value === false || value === "0";
  if ((!on && !off) || (operator !== "equals" && operator !== "not equals")) {
    throw new SyntaxError("A Check is on or off");
  }
  return row(name, "equals", on === (operator === "equals") ? "Yes" : "No");
}

function documentStatus(value: string | number | boolean): string {
  const status = DOCUMENT_STATUSES[Number(value)];
  if (typeof value === "boolean" || value === "" || !status)
    throw new SyntaxError("docstatus is 0, 1 or 2");
  return status;
}

function isYesNo(value: unknown) {
  return value === "Yes" || value === "No";
}
