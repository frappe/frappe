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
  /** Raw DocField default, carried verbatim; `newRowValues` resolves it. */
  default?: string;
  /** Decimal places for numeric fields (Float/Currency/Percent); from meta. */
  precision?: number;
  /** Initial grid-column width in px for a child-table column; omit for flexible. */
  width?: number;
  description?: string;
  placeholder?: string;
  /** Static visibility; `resolveLayout` may flip this from `dependsOn`. */
  hidden?: boolean;
  /** Field-level permission level, carried through from the DocField. Read for
   *  reporting only — on its own it does not mean the reader was denied. */
  permlevel?: number;
  /**
   * Whether the permlevel gate actually denied this reader. The denial is
   * expressed as a static `hidden` / `readOnly`, indistinguishable from a
   * meta-hidden or meta-read-only field, so this flag is what marks the
   * permission floor `resolveLayout` will not let an override lift.
   *
   * Only whoever applied the gate can set it — a `permlevel` alone is not a
   * denial (a reader who has the level is left untouched), and a layout built
   * without any gate has no floor to defend.
   */
  permDenied?: boolean;
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

/** Where a child row sits: its table's fieldname plus `name ?? __row_id`. */
export interface RowAddress {
  parentfield: string;
  key: string;
}

export type RowChange = "add" | "remove";

/**
 * Carries a field's *commit* (blur for typed inputs, selection for pickers) and
 * a child table's structural edits out to whoever owns events, so they are
 * dispatched at the mutation site instead of diffed out of the document.
 *
 * The value travels even though the doc already holds it: a control that
 * re-emits its value on commit (frappe-ui's `TextInput` binds `@input` and
 * `@change` to the same handler) would otherwise leave an edit looking pending
 * forever, and the next save would fire the handler a second time.
 */
export interface CommitChannel {
  /** A live edit whose commit has not arrived yet; `flush` fires it on save. */
  pending(fieldname: string, value: any, row?: RowAddress): void;
  commit(fieldname: string, value: any, row?: RowAddress): void;
  rowChanged(row: RowAddress, change: RowChange): void;
}

/** For a form whose document nothing scripts — a create dialog, a story. */
export const NO_COMMIT: CommitChannel = {
  pending: () => {},
  commit: () => {},
  rowChanged: () => {},
};

/**
 * Provided by whoever owns the document's events, above the layout. Mandatory:
 * a form with no provider silently drops every commit, so the absence is a
 * DEV error and `NO_COMMIT` is how a form says it meant it.
 */
export const CommitKey: InjectionKey<CommitChannel> = Symbol("FormLayoutCommit");
