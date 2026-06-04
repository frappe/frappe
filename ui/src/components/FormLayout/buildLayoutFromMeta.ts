import type {
  Column,
  FieldMeta,
  FormLayoutSchema,
  RawMetaField,
  Section,
  Tab,
} from './types'

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

const TAB_BREAK = 'Tab Break'
const SECTION_BREAK = 'Section Break'
const COLUMN_BREAK = 'Column Break'

function newColumn(field?: RawMetaField): Column {
  return { name: field?.fieldname, label: field?.label, fields: [] }
}

function newSection(field?: RawMetaField): Section {
  if (!field) return { columns: [] }
  const collapsible = !!field.collapsible
  return {
    name: field.fieldname,
    label: field.label,
    hideBorder: !!field.hide_border,
    collapsible,
    // No `opened` flag exists in meta; collapsible sections start collapsed
    // (Frappe desk behaviour). Phase 4 may refine this from `*_depends_on`.
    opened: !collapsible,
    columns: [],
  }
}

function mapField(field: RawMetaField): FieldMeta {
  return {
    fieldname: field.fieldname,
    fieldtype: field.fieldtype,
    label: field.label,
    options: field.options,
    filters: field.filters,
    reqd: !!field.reqd,
    description: field.description,
    hidden: !!field.hidden,
    dependsOn: field.depends_on,
    mandatoryDependsOn: field.mandatory_depends_on,
    readOnlyDependsOn: field.read_only_depends_on,
  }
}

export function buildLayoutFromMeta(fields: RawMetaField[]): FormLayoutSchema {
  if (!fields.length) return []

  const tabs: Tab[] = []

  // Containers are seeded lazily so a field/column/section appearing before its
  // first break still lands somewhere, without producing empty leading
  // containers when a break comes first.
  const ensureTab = (): Tab => {
    if (!tabs.length) tabs.push({ name: 'first_tab', sections: [] })
    return tabs[tabs.length - 1]
  }
  const ensureSection = (): Section => {
    const tab = ensureTab()
    if (!tab.sections.length) tab.sections.push(newSection())
    return tab.sections[tab.sections.length - 1]
  }
  const ensureColumn = (): Column => {
    const section = ensureSection()
    if (!section.columns.length) section.columns.push(newColumn())
    return section.columns[section.columns.length - 1]
  }

  for (const field of fields) {
    if (field.fieldtype === TAB_BREAK) {
      tabs.push({ name: field.fieldname, label: field.label, sections: [] })
    } else if (field.fieldtype === SECTION_BREAK) {
      ensureTab().sections.push(newSection(field))
    } else if (field.fieldtype === COLUMN_BREAK) {
      ensureSection().columns.push(newColumn(field))
    } else {
      if (field.hidden) continue // drop statically hidden fields
      ensureColumn().fields.push(mapField(field))
    }
  }

  return tabs
}
