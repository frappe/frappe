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
  /** Target doctype for `Link` fields (Frappe `options`). */
  options?: string
  /** Link search filters. */
  filters?: Record<string, unknown>
  /** Whether the field is mandatory. */
  reqd?: boolean
  description?: string
  placeholder?: string
  /** Static visibility; conditional `depends_on` is out of scope (see PLAN). */
  hidden?: boolean
  /**
   * Raw Frappe conditional expressions, carried through verbatim from meta.
   * Phase 2 does **not** evaluate these — `FormLayout` stays render-only and
   * Phase 4 will bake resolved visibility into the schema.
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
  hidden?: boolean | 0 | 1
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
  columns: Column[]
}

export interface Tab {
  name?: string
  label?: string
  hidden?: boolean
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
  'update:modelValue': [value: any]
}

/** The doc object fields read/write, provided from the root. */
export const DocKey: InjectionKey<Ref<Record<string, any>>> = Symbol('FormLayoutDoc')

/** Called by a field when its value changes: `(fieldname, value)`. */
export const ChangeKey: InjectionKey<(fieldname: string, value: any) => void> =
  Symbol('FormLayoutChange')

/** Resolves a fieldtype to its component (falls back to the text component). */
export const ResolveFieldKey: InjectionKey<(fieldtype: string) => Component> =
  Symbol('FormLayoutResolveField')

/** Whether the layout renders a visible tab strip (drives section padding). */
export const HasTabsKey: InjectionKey<Ref<boolean>> = Symbol('FormLayoutHasTabs')
