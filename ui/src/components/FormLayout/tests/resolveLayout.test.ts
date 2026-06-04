import { describe, expect, it } from 'vitest'
import { resolveLayout } from '../resolveLayout'
import type { FormLayoutSchema } from '../types'

const schema: FormLayoutSchema = [
  {
    name: 'main',
    label: 'Main',
    dependsOn: 'eval:doc.show_tab',
    sections: [
      {
        name: 'sec',
        label: 'Section',
        dependsOn: 'eval:doc.show_section',
        columns: [
          {
            name: 'col',
            fields: [
              { fieldname: 'a', fieldtype: 'Data', dependsOn: 'eval:doc.show_a' },
              { fieldname: 'b', fieldtype: 'Data', mandatoryDependsOn: 'eval:doc.need_b' },
              { fieldname: 'c', fieldtype: 'Data', readOnlyDependsOn: 'eval:doc.lock_c' },
            ],
          },
        ],
      },
    ],
  },
]

const fieldByName = (layout: FormLayoutSchema, name: string) =>
  layout[0].sections[0].columns[0].fields.find((f) => f.fieldname === name)!

describe('resolveLayout', () => {
  it('hides a field when its depends_on is false and shows it when true', () => {
    expect(fieldByName(resolveLayout(schema, { show_a: true }), 'a').hidden).toBe(false)
    expect(fieldByName(resolveLayout(schema, { show_a: false }), 'a').hidden).toBe(true)
  })

  it('hides a section when its depends_on is false', () => {
    expect(resolveLayout(schema, { show_section: true })[0].sections[0].hidden).toBe(false)
    expect(resolveLayout(schema, { show_section: false })[0].sections[0].hidden).toBe(true)
  })

  it('hides a tab when its depends_on is false', () => {
    expect(resolveLayout(schema, { show_tab: true })[0].hidden).toBe(false)
    expect(resolveLayout(schema, { show_tab: false })[0].hidden).toBe(true)
  })

  it('flips reqd from mandatory_depends_on', () => {
    expect(fieldByName(resolveLayout(schema, { need_b: true }), 'b').reqd).toBe(true)
    expect(fieldByName(resolveLayout(schema, { need_b: false }), 'b').reqd).toBe(false)
  })

  it('flips readOnly from read_only_depends_on', () => {
    expect(fieldByName(resolveLayout(schema, { lock_c: true }), 'c').readOnly).toBe(true)
    expect(fieldByName(resolveLayout(schema, { lock_c: false }), 'c').readOnly).toBe(false)
  })

  it('preserves a statically reqd / readOnly field regardless of conditions', () => {
    const s: FormLayoutSchema = [
      {
        sections: [
          {
            columns: [
              { fields: [{ fieldname: 'x', fieldtype: 'Data', reqd: true, readOnly: true }] },
            ],
          },
        ],
      },
    ]
    const x = fieldByName(resolveLayout(s, {}), 'x')
    expect(x.reqd).toBe(true)
    expect(x.readOnly).toBe(true)
  })

  it('does not mutate the input schema (purity)', () => {
    const before = JSON.parse(JSON.stringify(schema))
    resolveLayout(schema, { show_a: false, show_section: false, need_b: true, lock_c: true })
    expect(schema).toEqual(before)
  })
})
