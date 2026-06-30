import type { Component, InjectionKey, Ref } from "vue";

/**
 * Schema describing a doc form as a tree of tabs → sections → columns → fields.
 * `FormLayout` is render-only: it consumes a ready schema and does not fetch
 * doctype meta. Keys are camelCase; field-level keys mirror Frappe meta.
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
 * App-supplied presentation/behavior for one field's *layout node* — not part of
 * the portable `FieldMeta`. Filled by the build step (inline on a static schema,
 * or via `buildLayoutFromMeta`'s `decorate` hook); consumed by `FormLayoutField`,
 * which v-binds `props` and v-on's `on` onto the resolved field component (or
 * swaps the component entirely via `component`). Frappe meta never carries this.
 */
export interface FieldUI {
  /** Structural swap for THIS node only (e.g. a themed Button). */
  component?: Component;
  /** Presentation props v-bound onto the control (variant / theme / size …). */
  props?: Record<string, unknown>;
  /**
   * Event listeners v-on'd onto the control (`click`, `change`, …). A value
   * passed as a handler array fires every handler — `decorate` composition
   * concats per-event handlers so styling + scripting both run (see `compose`).
   * In a grid cell the row is injected as a trailing arg: `on.click(event, row)`.
   */
  on?: Record<
    string,
    ((...args: any[]) => void) | ((...args: any[]) => void)[]
  >;
}

/**
 * A field as it sits in the layout tree: its portable meta plus an optional,
 * app-supplied UI overlay. Extends `FieldMeta`, so every existing read
 * (`f.hidden`, `f.fieldname`) and every `{ ...f }` spread keeps working and the
 * `ui` key rides along untouched.
 */
export type FieldNode = FieldMeta & { ui?: FieldUI };

/**
 * The subset of a Frappe DocField (as returned by `getdoctype`) that
 * `buildLayoutFromMeta` reads. Booleans arrive as `0 | 1` from the backend.
 */
export interface RawMetaField {
  fieldname: string;
  fieldtype: string;
  label?: string;
  options?: string;
  reqd?: boolean | 0 | 1;
  /** Decimal places; arrives as a number or numeric string from the backend. */
  precision?: number | string;
  hidden?: boolean | 0 | 1;
  read_only?: boolean | 0 | 1;
  /** Whether a child-table field shows as a grid column. */
  in_list_view?: boolean | 0 | 1;
  description?: string;
  hide_border?: boolean | 0 | 1;
  collapsible?: boolean | 0 | 1;
  default?: string;
  depends_on?: string;
  mandatory_depends_on?: string;
  read_only_depends_on?: string;
  filters?: Record<string, unknown>;
}

export interface Column {
  name?: string;
  label?: string;
  hideLabel?: boolean;
  fields: FieldNode[];
}

export interface Section {
  name?: string;
  label?: string;
  hideLabel?: boolean;
  hideBorder?: boolean;
  opened?: boolean;
  collapsible?: boolean;
  hidden?: boolean;
  /** Conditional visibility; `resolveLayout` bakes it into `hidden`. */
  dependsOn?: string;
  columns: Column[];
}

export interface Tab {
  name?: string;
  label?: string;
  hidden?: boolean;
  /** Conditional visibility; `resolveLayout` bakes it into `hidden`. */
  dependsOn?: string;
  sections: Section[];
}

export type FormLayoutSchema = Tab[];

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

/** Resolves a fieldtype to its component (falls back to the text component). */
export const ResolveFieldKey: InjectionKey<(fieldtype: string) => Component> =
  Symbol("FormLayoutResolveField");

/** Whether the layout renders a visible tab strip (drives section padding). */
export const HasTabsKey: InjectionKey<Ref<boolean>> =
  Symbol("FormLayoutHasTabs");
