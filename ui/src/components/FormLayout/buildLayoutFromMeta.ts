import type {
  Column,
  FieldMeta,
  FieldNode,
  FieldUI,
  FormLayoutSchema,
  RawMetaField,
  Section,
  Tab,
} from "./types";

/**
 * Build a render-ready `FormLayoutSchema` from a doctype's flat meta `fields`,
 * splitting on layout breaks into the tabs → sections → columns → fields tree.
 * Pure (no Vue/backend). Static visibility only — carries `depends_on` verbatim
 * for Phase 4 rather than evaluating it. Statically-`hidden` data fields are kept
 * in the schema (filtered out at render time) so meta-script ops can target them;
 * layout-break fields are still dropped.
 */

const TAB_BREAK = "Tab Break";
const SECTION_BREAK = "Section Break";
const COLUMN_BREAK = "Column Break";
const TABLE = "Table";
const TABLE_MULTISELECT = "Table MultiSelect";

/** Fieldtypes whose value lives in a child table; both resolve `childFields`. */
const CHILD_TABLE_TYPES = new Set([TABLE, TABLE_MULTISELECT]);

/** Layout-break fieldtypes never render as a value/grid column. */
const LAYOUT_BREAKS = new Set([TAB_BREAK, SECTION_BREAK, COLUMN_BREAK]);

/**
 * App hook to attach per-field presentation/behavior during the build. Called
 * once per data field (and per grid column) with the field's resolved meta;
 * returns a `FieldUI` to overlay onto that node, or nothing to leave it plain.
 */
export type Decorator = (field: FieldMeta) => FieldUI | void;

export interface BuildLayoutOptions {
  /** Child doctype name → its flat meta `fields`, for resolving `Table` columns. */
  childMetas?: Record<string, RawMetaField[]>;
  /** Per-field UI overlay hook (see `Decorator`); inherited by nested grids. */
  decorate?: Decorator;
}

/**
 * Compose several decorators into one. Each is run against the field meta and
 * their returned overlays are merged: `component` is last-wins, `props` shallow-
 * merge, and `on` handlers **concat per event into an array so every handler
 * fires** (Vue's `v-on` accepts a handler array) — styling and scripting can
 * both contribute a `change`/`click` without one clobbering the other.
 */
export function compose(...decorators: Decorator[]): Decorator {
  return (field) => {
    let merged: FieldUI | undefined;
    for (const decorate of decorators) {
      const ui = decorate(field);
      if (!ui) continue;
      merged ??= {};
      if (ui.component) merged.component = ui.component;
      if (ui.props) merged.props = { ...merged.props, ...ui.props };
      if (ui.on) {
        const on = (merged.on ??= {});
        for (const [event, handler] of Object.entries(ui.on)) {
          const existing = on[event];
          on[event] = existing
            ? ([] as ((...a: any[]) => void)[])
                .concat(existing as any)
                .concat(handler as any)
            : handler;
        }
      }
    }
    return merged;
  };
}

function newColumn(field?: RawMetaField): Column {
  return { name: field?.fieldname, label: field?.label, fields: [] };
}

function newSection(field?: RawMetaField): Section {
  if (!field) return { columns: [] };
  const collapsible = !!field.collapsible;
  return {
    name: field.fieldname,
    label: field.label,
    hideBorder: !!field.hide_border,
    collapsible,
    // Collapsible sections start collapsed (Frappe desk behaviour).
    opened: !collapsible,
    dependsOn: field.depends_on,
    columns: [],
  };
}

const READ_ONLY = "Read Only";

/** Meta `precision` may be a number, a numeric string, or blank → `undefined`. */
function coercePrecision(
  precision: number | string | undefined
): number | undefined {
  if (precision == null || precision === "") return undefined;
  const n = Number(precision);
  return Number.isFinite(n) ? n : undefined;
}

/**
 * Resolve a `Table` field's grid columns from the child meta's `in_list_view`
 * fields (desk convention), falling back to all visible data fields so the grid
 * is never empty. `undefined` when the child meta is absent.
 */
function resolveChildFields(
  field: RawMetaField,
  childMetas: Record<string, RawMetaField[]>,
  decorate?: Decorator
): FieldNode[] | undefined {
  const childFields = field.options ? childMetas[field.options] : undefined;
  if (!childFields) return undefined;

  const dataFields = childFields.filter(
    (f) => !LAYOUT_BREAKS.has(f.fieldtype) && !f.hidden
  );
  const inListView = dataFields.filter((f) => f.in_list_view);
  const columns = inListView.length ? inListView : dataFields;
  return columns.map((f) => mapField(f, childMetas, decorate));
}

/**
 * Build the full child-doctype layout (every field) for the `Table` row-edit
 * dialog, which renders the whole child form (desk behaviour) rather than just
 * grid columns. `undefined` when the child meta is absent.
 */
function resolveChildLayout(
  field: RawMetaField,
  childMetas: Record<string, RawMetaField[]>,
  decorate?: Decorator
): FormLayoutSchema | undefined {
  const childMeta = field.options ? childMetas[field.options] : undefined;
  if (!childMeta) return undefined;
  return buildLayoutFromMeta(childMeta, { childMetas, decorate });
}

function mapField(
  field: RawMetaField,
  childMetas: Record<string, RawMetaField[]>,
  decorate?: Decorator
): FieldNode {
  const meta: FieldMeta = {
    fieldname: field.fieldname,
    fieldtype: field.fieldtype,
    label: field.label,
    options: field.options,
    filters: field.filters,
    reqd: !!field.reqd,
    precision: coercePrecision(field.precision),
    description: field.description,
    hidden: !!field.hidden,
    // The `Read Only` fieldtype is always read-only; conditional read-only is
    // baked in `resolveLayout`.
    readOnly: !!field.read_only || field.fieldtype === READ_ONLY,
    dependsOn: field.depends_on,
    mandatoryDependsOn: field.mandatory_depends_on,
    readOnlyDependsOn: field.read_only_depends_on,
    // Child-table columns. Nested grids aren't supported (no deeper childMetas).
    ...(CHILD_TABLE_TYPES.has(field.fieldtype)
      ? { childFields: resolveChildFields(field, childMetas, decorate) }
      : {}),
    // The row-edit dialog renders the full child form; `Table MultiSelect` has
    // no row dialog, so only `Table` carries a `childLayout`.
    ...(field.fieldtype === TABLE
      ? { childLayout: resolveChildLayout(field, childMetas, decorate) }
      : {}),
  };
  // Attach the app's per-field overlay (presentation/behavior); plain when absent.
  const ui = decorate?.(meta);
  return ui ? { ...meta, ui } : meta;
}

export function buildLayoutFromMeta(
  fields: RawMetaField[],
  options: BuildLayoutOptions = {}
): FormLayoutSchema {
  const { childMetas = {}, decorate } = options;
  if (!fields.length) return [];

  const tabs: Tab[] = [];

  // Lazy seeding: a field before its first break still lands somewhere, with no
  // empty leading containers when a break comes first.
  const ensureTab = (): Tab => {
    if (!tabs.length) tabs.push({ name: "first_tab", sections: [] });
    return tabs[tabs.length - 1];
  };
  const ensureSection = (): Section => {
    const tab = ensureTab();
    if (!tab.sections.length) tab.sections.push(newSection());
    return tab.sections[tab.sections.length - 1];
  };
  const ensureColumn = (): Column => {
    const section = ensureSection();
    if (!section.columns.length) section.columns.push(newColumn());
    return section.columns[section.columns.length - 1];
  };

  for (const field of fields) {
    if (field.fieldtype === TAB_BREAK) {
      tabs.push({
        name: field.fieldname,
        label: field.label,
        dependsOn: field.depends_on,
        sections: [],
      });
    } else if (field.fieldtype === SECTION_BREAK) {
      ensureTab().sections.push(newSection(field));
    } else if (field.fieldtype === COLUMN_BREAK) {
      ensureSection().columns.push(newColumn(field));
    } else {
      // Keep statically-hidden data fields in the schema (`mapField` marks them
      // `hidden`, and `FormLayoutColumn` filters them out at render time) rather
      // than dropping them here — so `applyMetaScript` ops (`showField`, or
      // `addField` with `after:` a hidden field) can still target them instead
      // of silently no-op'ing on a field that was never in the schema.
      ensureColumn().fields.push(mapField(field, childMetas, decorate));
    }
  }

  return tabs;
}
