import type { Component, InjectionKey, Ref } from "vue";
// The field contract (`FieldMeta`, `FieldComponentProps`, `FieldComponentEmits`)
// and the form-context injection keys (`DocKey`/`ParentDocKey`/`UpdateKey`) now
// live with the shared value-inputs (ADR-0004). Re-exported here so existing
// `from ".../FormLayout/types"` and `@framework/ui/FormLayout` imports keep working.
import type { FieldMeta } from "../Fields/types";
export type {
  FieldMeta,
  FieldComponentProps,
  FieldComponentEmits,
} from "../Fields/types";
export { DocKey, ParentDocKey, UpdateKey } from "../Fields/types";

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
  /** Whether the field is surfaced as a default Quick Filter input (the
   *  `in_standard_filter` flag CRM's `get_quick_filters` reads). */
  in_standard_filter?: boolean | 0 | 1;
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

/** Resolves a fieldtype to its component (falls back to the text component). */
export const ResolveFieldKey: InjectionKey<(fieldtype: string) => Component> =
  Symbol("FormLayoutResolveField");

/** Whether the layout renders a visible tab strip (drives section padding). */
export const HasTabsKey: InjectionKey<Ref<boolean>> =
  Symbol("FormLayoutHasTabs");
