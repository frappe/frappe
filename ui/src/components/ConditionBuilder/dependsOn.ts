// Reading and writing a DocField's condition (`depends_on`, `mandatory_depends_on`,
// `read_only_depends_on`, `collapsible_depends_on`): a bare fieldname or `eval:`
// JavaScript with `doc` and `parent`. The builder shows the simple subset; any
// other condition reads as null, so the host keeps it as code, as written.
import type { FieldMeta } from "../Fields/types";
import { conditionOperators } from "./internal/operators";
import { DependsOnReader } from "./internal/dependsOnReader";
import {
  DOCUMENT_STATUS,
  DOCUMENT_STATUSES,
  RECORD_IS_NEW,
} from "./internal/dependsOnRules";
import { DependsOnWriter } from "./internal/dependsOnWriter";
import { t } from "./internal/translate";
import { emptyTree, isGroup } from "./tree";
import type {
  ConditionField,
  ConditionGroup,
  DependsOnScope,
  FieldConditionValue,
} from "./types";

type Tree = ConditionGroup<FieldConditionValue>;
type ScopeField = Pick<
  FieldMeta,
  "fieldname" | "fieldtype" | "label" | "options"
>;

export { fieldReference, referencedField } from "./internal/dependsOnRules";

const TABLE_FIELDTYPES = ["Table", "Table MultiSelect"];
const NO_VALUE_FIELDTYPES = [
  "Section Break",
  "Column Break",
  "Tab Break",
  "HTML",
  "Button",
  "Heading",
  "Image",
  "Fold",
];

/**
 * What a condition may name: the fields, a child row's parent fields as
 * `parent.x`, "Record is new", and "Document status" on a submittable DocType.
 */
export function dependsOnScope(
  fields: ScopeField[],
  options: { parentFields?: ScopeField[]; submittable?: boolean } = {}
): DependsOnScope {
  const tables = new Set<string>();
  const offered: ConditionField[] = [];
  const offer = (field: ScopeField, parent: boolean) => {
    if (NO_VALUE_FIELDTYPES.includes(field.fieldtype) || !field.fieldname)
      return;
    const fieldname = parent ? `parent.${field.fieldname}` : field.fieldname;
    const label = field.label || field.fieldname;
    if (TABLE_FIELDTYPES.includes(field.fieldtype)) tables.add(fieldname);
    offered.push(
      scopeField(fieldname, parent ? t("Parent: {0}", [label]) : label, field)
    );
  };
  fields.forEach((field) => offer(field, false));
  options.parentFields?.forEach((field) => offer(field, true));

  offered.push(specialField(RECORD_IS_NEW, t("Record is new"), "Check"));
  if (options.submittable) {
    const statuses = DOCUMENT_STATUSES.join("\n");
    offered.push(
      specialField(DOCUMENT_STATUS, t("Document status"), "Select", statuses)
    );
  }
  return { fields: offered, tables };
}

/** A condition as a tree, or null when the builder cannot show it unchanged. */
export function fromDependsOn(
  condition: string | null | undefined,
  scope: DependsOnScope
): Tree | null {
  const text = (condition ?? "").trim();
  const code = text.startsWith("eval:") ? text.slice(5).trim() : null;
  if (!text || code === "") return emptyTree();
  try {
    const node =
      code === null
        ? bareField(text, scope)
        : new DependsOnReader(code, scope).read();
    return isGroup(node) ? node : { conjunction: "and", conditions: [node] };
  } catch (error) {
    if (error instanceof SyntaxError) return null;
    throw error;
  }
}

/** A tree as a condition. Unfinished rows are dropped, as on any save. */
export function toDependsOn(tree: Tree | null, scope: DependsOnScope): string {
  return new DependsOnWriter(scope).write(tree ?? emptyTree());
}

// Helpers

function bareField(text: string, scope: DependsOnScope) {
  if (!/^\w+$/.test(text)) throw new SyntaxError("Not a fieldname");
  return DependsOnReader.field(text, scope);
}

function scopeField(
  fieldname: string,
  label: string,
  field: ScopeField
): ConditionField {
  if (TABLE_FIELDTYPES.includes(field.fieldtype)) {
    return {
      label: t("{0} (has rows)", [label]),
      value: fieldname,
      fieldname,
      fieldtype: "Check",
    };
  }
  // A type with no operators of its own (Phone, Attach, Read Only) reads as text.
  const fieldtype = conditionOperators(field.fieldtype).length
    ? field.fieldtype
    : "Data";
  return {
    label,
    value: fieldname,
    fieldname,
    fieldtype,
    options: field.options,
  };
}

function specialField(
  fieldname: string,
  label: string,
  fieldtype: string,
  options?: string
) {
  return {
    label,
    value: fieldname,
    fieldname,
    fieldtype,
    options,
  } as ConditionField;
}
