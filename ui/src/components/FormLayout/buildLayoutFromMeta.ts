import type {
  Column,
  FieldMeta,
  FormLayoutSchema,
  RawMetaField,
  Section,
  Tab,
} from "./types";

/**
 * Build a render-ready `FormLayoutSchema` from a doctype's flat meta `fields`
 * array. Walks the list and splits on layout breaks into the nested
 * tabs → sections → columns → fields tree, mapping snake_case meta to our
 * camelCase keys.
 *
 * Pure: no Vue, no backend — unit-testable in isolation. Visibility is static
 * only (drops `hidden` fields); `depends_on` family expressions are carried
 * through verbatim for Phase 4, not evaluated here.
 */

const TAB_BREAK = "Tab Break";
const SECTION_BREAK = "Section Break";
const COLUMN_BREAK = "Column Break";
const TABLE = "Table";
const TABLE_MULTISELECT = "Table MultiSelect";

/** Fieldtypes whose value lives in a child table — both resolve `childFields`
 *  from the child doctype meta (the grid columns for `Table`, the single Link
 *  field for `Table MultiSelect`). */
const CHILD_TABLE_TYPES = new Set([TABLE, TABLE_MULTISELECT]);

/** Layout-break fieldtypes never render as a value/grid column. */
const LAYOUT_BREAKS = new Set([TAB_BREAK, SECTION_BREAK, COLUMN_BREAK]);

/** Lookup of child doctype name → its flat meta `fields`, for resolving
 *  `Table` columns. Supplied by the meta-fetch seam (`useDoctypeLayout`). */
export interface BuildLayoutOptions {
  childMetas?: Record<string, RawMetaField[]>;
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
    // No `opened` flag exists in meta; collapsible sections start collapsed
    // (Frappe desk behaviour). Refining this from `*_depends_on` is out of
    // scope for Phase 4.
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
 * Resolve a `Table` field's grid columns from the child doctype's meta. Uses the
 * child's `in_list_view` fields (the desk grid convention); if none are flagged,
 * falls back to every visible data field so the grid is never empty. Returns
 * `undefined` when the child meta is absent — the grid then renders no columns.
 */
function resolveChildFields(
  field: RawMetaField,
  childMetas: Record<string, RawMetaField[]>
): FieldMeta[] | undefined {
  const childFields = field.options ? childMetas[field.options] : undefined;
  if (!childFields) return undefined;

  const dataFields = childFields.filter(
    (f) => !LAYOUT_BREAKS.has(f.fieldtype) && !f.hidden
  );
  const inListView = dataFields.filter((f) => f.in_list_view);
  const columns = inListView.length ? inListView : dataFields;
  return columns.map((f) => mapField(f, childMetas));
}

/**
 * Build the full layout of a `Table` field's child doctype — its own
 * tabs/sections/columns, every field, not just the grid columns. Drives the
 * row-edit dialog, which renders the whole child form (desk behaviour) rather
 * than the `in_list_view` subset shown as grid columns. Returns `undefined`
 * when the child meta is absent.
 */
function resolveChildLayout(
  field: RawMetaField,
  childMetas: Record<string, RawMetaField[]>
): FormLayoutSchema | undefined {
  const childMeta = field.options ? childMetas[field.options] : undefined;
  if (!childMeta) return undefined;
  return buildLayoutFromMeta(childMeta, { childMetas });
}

function mapField(
  field: RawMetaField,
  childMetas: Record<string, RawMetaField[]>
): FieldMeta {
  return {
    fieldname: field.fieldname,
    fieldtype: field.fieldtype,
    label: field.label,
    options: field.options,
    filters: field.filters,
    reqd: !!field.reqd,
    precision: coercePrecision(field.precision),
    description: field.description,
    hidden: !!field.hidden,
    // The `Read Only` fieldtype is permanently read-only; static `read_only`
    // covers every other type. Conditional read-only is baked in `resolveLayout`.
    readOnly: !!field.read_only || field.fieldtype === READ_ONLY,
    dependsOn: field.depends_on,
    mandatoryDependsOn: field.mandatory_depends_on,
    readOnlyDependsOn: field.read_only_depends_on,
    // Child-table columns. Nested grids aren't supported, so a `Table` inside a
    // child meta resolves with no further recursion (its own childMetas lookup
    // simply won't contain a deeper level).
    ...(CHILD_TABLE_TYPES.has(field.fieldtype)
      ? { childFields: resolveChildFields(field, childMetas) }
      : {}),
    // The row-edit dialog renders the full child form; `Table MultiSelect` has
    // no row dialog, so only `Table` carries a `childLayout`.
    ...(field.fieldtype === TABLE
      ? { childLayout: resolveChildLayout(field, childMetas) }
      : {}),
  };
}

export function buildLayoutFromMeta(
  fields: RawMetaField[],
  options: BuildLayoutOptions = {}
): FormLayoutSchema {
  const { childMetas = {} } = options;
  if (!fields.length) return [];

  const tabs: Tab[] = [];

  // Containers are seeded lazily so a field/column/section appearing before its
  // first break still lands somewhere, without producing empty leading
  // containers when a break comes first.
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
      if (field.hidden) continue; // drop statically hidden fields
      ensureColumn().fields.push(mapField(field, childMetas));
    }
  }

  return tabs;
}
