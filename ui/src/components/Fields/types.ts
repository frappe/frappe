import type { InjectionKey, Ref } from "vue";
// Type-only (erased at build) — `FieldMeta`'s Table fields carry FormLayout's
// richer node/schema, while `FieldNode extends FieldMeta`. The cycle is purely
// at the type level, so it disappears in the compiled output.
import type { FieldNode, FormLayoutSchema } from "../FormLayout/types";

/**
 * The portable meta a value-input reads. A subset of a Frappe DocField, shared by
 * both `FormLayout` (form fields) and the ListView `Filter` / `Quick Filter`
 * controls. `FieldNode` (FormLayout's layout node) extends this with a `ui` overlay.
 */
export interface FieldMeta {
  fieldname: string;
  fieldtype: string;
  label?: string;
  /** Target doctype for `Link` fields, or child doctype for `Table` (Frappe `options`). */
  options?: string;
  /** Link search filters. */
  filters?: Record<string, unknown>;
  /**
   * Child-table columns from the child's `in_list_view` fields. Used by `Table`
   * (grid columns) and `Table MultiSelect` (its single `Link` field gives the
   * target doctype + per-row value key). Typed `FieldNode[]` so grid columns
   * carry a `ui` overlay too — back-compatible since `FieldNode extends FieldMeta`.
   */
  childFields?: FieldNode[];
  /**
   * Full render-ready layout of the child doctype, for the `Table` row-edit
   * dialog which shows every field (desk grid-row form), not just the
   * `in_list_view` columns in `childFields`.
   */
  childLayout?: FormLayoutSchema;
  /** Whether the field is mandatory. */
  reqd?: boolean;
  /** Decimal places for numeric fields (Float/Currency/Percent); from meta. */
  precision?: number;
  /** Initial grid-column width in px for a child-table column; omit for flexible. */
  width?: number;
  description?: string;
  placeholder?: string;
  /** Static visibility; `resolveLayout` may flip this from `dependsOn`. */
  hidden?: boolean;
  /** Static read-only; `resolveLayout` may flip this from `readOnlyDependsOn`. */
  readOnly?: boolean;
  /**
   * Raw Frappe conditional expressions, carried verbatim. Not evaluated here —
   * `resolveLayout` bakes them into `hidden` / `reqd` / `readOnly` (Phase 4).
   */
  dependsOn?: string;
  mandatoryDependsOn?: string;
  readOnlyDependsOn?: string;
}

/**
 * Contract every registered field component satisfies: it takes the field's
 * meta plus the current value, and emits value changes.
 */
export interface FieldComponentProps {
  field: FieldMeta;
  modelValue: any;
  row?: Record<string, any>;
}

export type FieldComponentEmits = {
  /** Live value on every change — keeps `doc` reactive while editing. */
  "update:modelValue": [value: any];
  /** Commit (blur for typed inputs, selection for pickers); only the field knows
   *  which event means commit. Caught by the node's `ui.on.change` when one is
   *  attached, otherwise a harmless no-op (the value is already synced into `doc`
   *  via `update:modelValue`). `FormLayout` itself emits nothing. */
  change: [value: any];
};

/** The doc object fields read/write, provided from the root. */
export const DocKey: InjectionKey<Ref<Record<string, any>>> =
  Symbol("FormLayoutDoc");

/**
 * Parent doc, provided by `TableField` into a row's edit dialog. The row's
 * nested `FormLayout` shadows `DocKey` with the row clone, so parent-scoped
 * resolution (e.g. a `Currency` `options` naming a parent field) needs this.
 * Absent at the top level — injectors must treat it as optional.
 */
export const ParentDocKey: InjectionKey<Ref<Record<string, any>> | null> =
  Symbol("FormLayoutParentDoc");

/** Writes a field's live value into the doc on every change. Pure state sync. */
export const UpdateKey: InjectionKey<(fieldname: string, value: any) => void> =
  Symbol("FormLayoutUpdate");
