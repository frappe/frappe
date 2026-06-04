import { describe, expect, it } from 'vitest'
import { buildLayoutFromMeta } from '../buildLayoutFromMeta'
import type { RawMetaField } from '../types'

const field = (over: Partial<RawMetaField>): RawMetaField => ({
  fieldname: 'f',
  fieldtype: 'Data',
  ...over,
})

describe('buildLayoutFromMeta', () => {
  it('returns an empty schema for no fields', () => {
    expect(buildLayoutFromMeta([])).toEqual([])
  })

  it('seeds one implicit tab/section/column for a flat list with no breaks', () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: 'a' }),
      field({ fieldname: 'b' }),
    ])

    expect(layout).toHaveLength(1)
    expect(layout[0].sections).toHaveLength(1)
    expect(layout[0].sections[0].columns).toHaveLength(1)
    expect(layout[0].sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual(
      ['a', 'b'],
    )
  })

  it('a leading field before any break lands in the seeded container', () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: 'lead' }),
      field({ fieldname: 'tab', fieldtype: 'Tab Break', label: 'Tab 2' }),
      field({ fieldname: 'after' }),
    ])

    expect(layout).toHaveLength(2)
    expect(layout[0].sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual([
      'lead',
    ])
    expect(layout[1].label).toBe('Tab 2')
    expect(layout[1].sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual([
      'after',
    ])
  })

  it('nests Tab / Section / Column breaks correctly', () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: 's1', fieldtype: 'Section Break', label: 'S1' }),
      field({ fieldname: 'a' }),
      field({ fieldname: 'c1', fieldtype: 'Column Break' }),
      field({ fieldname: 'b' }),
      field({ fieldname: 't2', fieldtype: 'Tab Break', label: 'Tab 2' }),
      field({ fieldname: 's2', fieldtype: 'Section Break', label: 'S2' }),
      field({ fieldname: 'c' }),
    ])

    expect(layout).toHaveLength(2)

    // Tab 1: section S1 with two columns (a | b)
    const tab1 = layout[0]
    expect(tab1.sections).toHaveLength(1)
    expect(tab1.sections[0].label).toBe('S1')
    expect(tab1.sections[0].columns).toHaveLength(2)
    expect(tab1.sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual(['a'])
    expect(tab1.sections[0].columns[1].fields.map((f) => f.fieldname)).toEqual(['b'])

    // Tab 2: section S2 with one column (c)
    const tab2 = layout[1]
    expect(tab2.label).toBe('Tab 2')
    expect(tab2.sections[0].label).toBe('S2')
    expect(tab2.sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual(['c'])
  })

  it('maps section-break attributes (hideBorder, collapsible, opened)', () => {
    const layout = buildLayoutFromMeta([
      field({
        fieldname: 's',
        fieldtype: 'Section Break',
        label: 'More',
        hide_border: 1,
        collapsible: 1,
      }),
      field({ fieldname: 'a' }),
    ])

    const section = layout[0].sections[0]
    expect(section.label).toBe('More')
    expect(section.hideBorder).toBe(true)
    expect(section.collapsible).toBe(true)
    // collapsible sections start collapsed
    expect(section.opened).toBe(false)
  })

  it('drops statically hidden fields', () => {
    const layout = buildLayoutFromMeta([
      field({ fieldname: 'visible' }),
      field({ fieldname: 'secret', hidden: 1 }),
    ])

    expect(layout[0].sections[0].columns[0].fields.map((f) => f.fieldname)).toEqual([
      'visible',
    ])
  })

  it('maps snake_case meta to camelCase and carries depends_on through as a string', () => {
    const layout = buildLayoutFromMeta([
      field({
        fieldname: 'owner',
        fieldtype: 'Link',
        label: 'Owner',
        options: 'User',
        reqd: 1,
        depends_on: 'eval:doc.status == "Open"',
        mandatory_depends_on: 'eval:doc.priority == "High"',
        read_only_depends_on: 'eval:doc.locked',
      }),
    ])

    const f = layout[0].sections[0].columns[0].fields[0]
    expect(f.fieldtype).toBe('Link')
    expect(f.options).toBe('User')
    expect(f.reqd).toBe(true)
    expect(f.dependsOn).toBe('eval:doc.status == "Open"')
    expect(f.mandatoryDependsOn).toBe('eval:doc.priority == "High"')
    expect(f.readOnlyDependsOn).toBe('eval:doc.locked')
  })
})
