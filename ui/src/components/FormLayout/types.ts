import type { Component, InjectionKey, Ref } from 'vue'

/**
 * Schema describing a doc form as a tree of tabs → sections → columns → fields.
 * `FormLayout` is render-only: it consumes a ready schema and does not fetch
 * doctype meta. Keys are camelCase; field-level keys mirror Frappe meta.
 */
export interface FieldMeta {
  fieldname: string
  fieldtype: string
  label?: string
  /** Target doctype for `Link` fields, or child doctype for `Table` (Frappe `options`). */
  options?: string
  /** Link search filters. */
  filters?: Record<string, unknown>
  /**
   * Resolved child-table columns for `Table` fields: the child doctype's
   * `in_list_view` fields, mapped through the same `FieldMeta` shape. Populated by
   * `buildLayoutFromMeta` from the child meta (`options` names the child doctype).
   * `FormLayout` stays render-only — the grid reuses the fieldtype registry per
   * cell, so it never fetches child meta itself.
   */
  childFields?: FieldMeta[]
  /** Whether the field is mandatory. */
  reqd?: boolean
  /** Decimal places for numeric fields (Float/Currency/Percent); from meta. */
  precision?: number
  description?: string
  placeholder?: string
  /** Static visibility; `resolveLayout` may flip this from `dependsOn`. */
  hidden?: boolean
  /** Static read-only; `resolveLayout` may flip this from `readOnlyDependsOn`. */
  readOnly?: boolean
  /**
   * Raw Frappe conditional expressions, carried through verbatim from meta.
   * `buildLayoutFromMeta` does **not** evaluate these — `resolveLayout` bakes
   * them into `hidden` / `reqd` / `readOnly` against the live doc (Phase 4).
   */
  dependsOn?: string
  mandatoryDependsOn?: string
  readOnlyDependsOn?: string
}

/**
 * The subset of a Frappe DocField (as returned by `getdoctype`) that
 * `buildLayoutFromMeta` reads. Booleans arrive as `0 | 1` from the backend.
 */
export interface RawMetaField {
  fieldname: string
  fieldtype: string
  label?: string
  options?: string
  reqd?: boolean | 0 | 1
  /** Decimal places; arrives as a number or numeric string from the backend. */
  precision?: number | string
  hidden?: boolean | 0 | 1
  read_only?: boolean | 0 | 1
  /** Whether a child-table field shows as a grid column. */
  in_list_view?: boolean | 0 | 1
  description?: string
  hide_border?: boolean | 0 | 1
  collapsible?: boolean | 0 | 1
  default?: string
  depends_on?: string
  mandatory_depends_on?: string
  read_only_depends_on?: string
  filters?: Record<string, unknown>
}

export interface Column {
  name?: string
  label?: string
  hideLabel?: boolean
  fields: FieldMeta[]
}

export interface Section {
  name?: string
  label?: string
  hideLabel?: boolean
  hideBorder?: boolean
  opened?: boolean
  collapsible?: boolean
  hidden?: boolean
  /** Conditional visibility; `resolveLayout` bakes it into `hidden`. */
  dependsOn?: string
  columns: Column[]
}

export interface Tab {
  name?: string
  label?: string
  hidden?: boolean
  /** Conditional visibility; `resolveLayout` bakes it into `hidden`. */
  dependsOn?: string
  sections: Section[]
}

export type FormLayoutSchema = Tab[]

/**
 * Contract every registered field component satisfies: it takes the field's
 * meta plus the current value, and emits value changes.
 */
export interface FieldComponentProps {
  field: FieldMeta
  modelValue: any
}

export type FieldComponentEmits = {
  /** Live value, on every change — keeps `doc` in sync so bindings and
   *  conditional visibility (`depends_on`) stay reactive while editing. */
  'update:modelValue': [value: any]
  /** Commit — the user finished editing this field: **blur** for typed inputs,
   *  **selection** for pickers. Only the field knows which event means "commit".
   *  This is the funnel the field-change scripting layer will hook; today it
   *  surfaces as `FormLayout`'s `@change`. */
  change: [value: any]
}

/** The doc object fields read/write, provided from the root. */
export const DocKey: InjectionKey<Ref<Record<string, any>>> = Symbol('FormLayoutDoc')

/**
 * Writes a field's live value into the doc: `(fieldname, value)`. Fires on every
 * value change so bindings and conditional visibility stay reactive. Pure state
 * sync — no side-effects, no scripts.
 */
export const UpdateKey: InjectionKey<(fieldname: string, value: any) => void> =
  Symbol('FormLayoutUpdate')

/**
 * Called when a field is **committed** (typed input blurred, picker selected):
 * `(fieldname, value)`. This is the intentful "the user changed this field"
 * signal — the entry point for the future field-change scripting layer (Frappe
 * `frm.trigger`-style on-change scripts), and what `FormLayout` surfaces as its
 * `@change` event. Distinct from value-sync because a script needs to know
 * *which* field the user committed, run only on commit, and may mutate siblings.
 */
export const CommitKey: InjectionKey<(fieldname: string, value: any) => void> =
  Symbol('FormLayoutCommit')

/** Resolves a fieldtype to its component (falls back to the text component). */
export const ResolveFieldKey: InjectionKey<(fieldtype: string) => Component> =
  Symbol('FormLayoutResolveField')

/** Whether the layout renders a visible tab strip (drives section padding). */
export const HasTabsKey: InjectionKey<Ref<boolean>> = Symbol('FormLayoutHasTabs')
