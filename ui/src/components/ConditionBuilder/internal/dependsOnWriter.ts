// Writing a builder tree as a `depends_on` condition: the bare fieldname when
// that is all it says, else `eval:` JavaScript in the forms `dependsOnReader`
// reads back as the same tree.
import { isGroup } from "../tree";
import type {
  ConditionGroup,
  ConditionNode,
  DependsOnScope,
  FieldConditionValue,
} from "../types";
import {
  DOCUMENT_STATUS,
  DOCUMENT_STATUSES,
  NUMBER_FIELDTYPES,
  RECORD_IS_NEW,
  referencedField,
} from "./dependsOnRules";

type Leaf = FieldConditionValue;
type Tree = ConditionGroup<Leaf>;

const JS_OPERATOR: Record<string, string> = {
  equals: "===",
  "not equals": "!==",
};
const SPECIAL_FIELDS = [RECORD_IS_NEW, DOCUMENT_STATUS];
/** A fieldname, so it is written into the code as a name and never as code. */
const FIELD_PATH = /^(parent\.)?[A-Za-z_$][\w$]*$/;

export class DependsOnWriter {
  constructor(private scope: DependsOnScope) {}

  write(tree: Tree): string {
    const root = this.prune(tree);
    if (!root.conditions.length) return "";
    const only = root.conditions.length === 1 ? root.conditions[0] : null;
    if (only && !isGroup(only) && this.isBareField(only))
      return checkedPath(only.fieldname);
    return `eval:${this.group(root)}`;
  }

  /**
   * The tree as it reads back: unfinished rows and empty groups dropped, a
   * group of one replaced by its row, and a root of one group by that group.
   */
  prune(tree: Tree): Tree {
    const conditions = tree.conditions.flatMap((node) => this.pruneNode(node));
    if (conditions.length === 1 && isGroup(conditions[0])) return conditions[0];
    return {
      conjunction: conditions.length > 1 ? tree.conjunction : "and",
      conditions,
    };
  }

  private pruneNode(node: ConditionNode<Leaf>): ConditionNode<Leaf>[] {
    if (!isGroup(node)) return this.isFinished(node) ? [node] : [];
    const group = this.prune(node);
    if (group.conditions.length > 1) return [group];
    return group.conditions;
  }

  private group(group: Tree): string {
    const several = group.conditions.length > 1;
    return group.conditions
      .map((node) => {
        if (!isGroup(node)) return this.leaf(node);
        return several ? `(${this.group(node)})` : this.group(node);
      })
      .join(group.conjunction === "or" ? " || " : " && ");
  }

  private leaf(leaf: Leaf): string {
    const ref = this.reference(leaf.fieldname);
    const not = (yes: boolean) => (yes ? "" : "!");
    if (
      this.isCheck(leaf.fieldname) &&
      isYesNo(leaf.value) &&
      leaf.operator === "equals"
    ) {
      return `${not(leaf.value === "Yes")}${ref}`;
    }
    switch (leaf.operator) {
      case "is":
      case "is not":
        return `${not(
          (leaf.operator === "is") === (leaf.value === "set")
        )}${ref}`;
      case "in":
      case "not in":
        return `${not(leaf.operator === "in")}[${this.list(
          leaf
        )}].includes(${ref})`;
      case "like":
      case "not like":
        return `${not(leaf.operator === "like")}${this.orEmpty(
          leaf.fieldname,
          ref
        )}.includes(${JSON.stringify(String(leaf.value))})`;
      case "between": {
        const [from, to] = listOf(leaf.value);
        const literal = (end: unknown) => this.literal(leaf.fieldname, end);
        return `(${literal(from)} <= ${ref} && ${ref} <= ${literal(to)})`;
      }
      default:
        return `${ref} ${
          JS_OPERATOR[leaf.operator] ?? leaf.operator
        } ${this.literal(leaf.fieldname, leaf.value)}`;
    }
  }

  private isBareField(leaf: Leaf): boolean {
    if (
      leaf.fieldname.startsWith("parent.") ||
      SPECIAL_FIELDS.includes(leaf.fieldname)
    )
      return false;
    if (leaf.operator === "is") return leaf.value === "set";
    return (
      this.isCheck(leaf.fieldname) &&
      leaf.operator === "equals" &&
      leaf.value === "Yes"
    );
  }

  /** A row still being filled in holds no condition, so dropping it is lossless. */
  private isFinished(leaf: Leaf): boolean {
    if (!leaf.fieldname) return false;
    const value = leaf.value;
    if (leaf.operator === "is" || leaf.operator === "is not")
      return value === "set" || value === "not set";
    if (leaf.operator === "in" || leaf.operator === "not in")
      return listOf(value).length > 0;
    if (leaf.operator === "between") return listOf(value).length === 2;
    if (leaf.operator === "like" || leaf.operator === "not like")
      return Boolean(value);
    return value !== null && value !== undefined;
  }

  private reference(fieldname: string): string {
    const path = checkedPath(fieldname);
    const ref = path.startsWith("parent.") ? path : `doc.${path}`;
    return this.scope.tables.has(fieldname) ? `${ref}.length` : ref;
  }

  /** `String(...)` for a number, which has no `includes`; `|| ""` reads simpler on text. */
  private orEmpty(fieldname: string, ref: string): string {
    return this.isNumber(fieldname) ? `String(${ref} ?? "")` : `(${ref} || "")`;
  }

  private list(leaf: Leaf): string {
    return listOf(leaf.value)
      .map((item) => this.literal(leaf.fieldname, item))
      .join(", ");
  }

  /** A value as code: a field it references, else text or a number. */
  private literal(fieldname: string, value: unknown): string {
    const field = referencedField(value);
    if (field && this.field(field) && !this.scope.tables.has(field))
      return this.reference(field);
    if (fieldname === DOCUMENT_STATUS)
      return String(DOCUMENT_STATUSES.indexOf(String(value)));
    const number = Number(value);
    if (this.isNumber(fieldname) && value !== "" && Number.isFinite(number))
      return String(number);
    return JSON.stringify(String(value ?? ""));
  }

  private isCheck(fieldname: string) {
    return this.field(fieldname)?.fieldtype === "Check";
  }

  private isNumber(fieldname: string) {
    return NUMBER_FIELDTYPES.includes(this.field(fieldname)?.fieldtype ?? "");
  }

  private field(fieldname: string) {
    return this.scope.fields.find((one) => one.fieldname === fieldname);
  }
}

function checkedPath(fieldname: string): string {
  if (!FIELD_PATH.test(fieldname))
    throw new Error(`Not a fieldname: ${fieldname}`);
  return fieldname;
}

/** A list value as its items: the picked values, or a comma string split. */
function listOf(value: unknown): unknown[] {
  if (Array.isArray(value))
    return value.filter((item) => item !== null && item !== "");
  if (typeof value !== "string") return [];
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function isYesNo(value: unknown) {
  return value === "Yes" || value === "No";
}
