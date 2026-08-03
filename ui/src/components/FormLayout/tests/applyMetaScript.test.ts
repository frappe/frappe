import { describe, expect, it } from 'vitest'
import { applyMetaScript } from '../applyMetaScript'
import type { MetaOp } from '../applyMetaScript'
import type { FormLayoutSchema } from '../types'

const schema: FormLayoutSchema = [
  {
    name: 'main',
    label: 'Main',
    sections: [
      {
        name: 'sec',
        label: 'Section',
        columns: [
          {
            name: 'col',
            fields: [
              { fieldname: 'a', fieldtype: 'Data', label: 'A' },
              { fieldname: 'b', fieldtype: 'Data', label: 'B' },
            ],
          },
        ],
      },
    ],
  },
]

const fields = (layout: FormLayoutSchema) => layout[0].sections[0].columns[0].fields
const fieldByName = (layout: FormLayoutSchema, name: string) =>
  fields(layout).find((f) => f.fieldname === name)!

describe('applyMetaScript', () => {
  it('sets an arbitrary field property by fieldname', () => {
    const out = applyMetaScript(schema, [
      { op: 'setFieldProperty', fieldname: 'a', prop: 'label', value: 'Renamed' },
    ])
    expect(fieldByName(out, 'a').label).toBe('Renamed')
    expect(fieldByName(out, 'b').label).toBe('B') // untouched
  })

  it('hides and shows a field', () => {
    const hidden = applyMetaScript(schema, [{ op: 'hideField', fieldname: 'b' }])
    expect(fieldByName(hidden, 'b').hidden).toBe(true)
    const shown = applyMetaScript(hidden, [{ op: 'showField', fieldname: 'b' }])
    expect(fieldByName(shown, 'b').hidden).toBe(false)
  })

  it('inserts a new field after an existing one', () => {
    const out = applyMetaScript(schema, [
      {
        op: 'addField',
        after: 'a',
        field: { fieldname: 'a2', fieldtype: 'Data', label: 'A2' },
      },
    ])
    expect(fields(out).map((f) => f.fieldname)).toEqual(['a', 'a2', 'b'])
  })

  it('applies ops in order', () => {
    const ops: MetaOp[] = [
      { op: 'setFieldProperty', fieldname: 'a', prop: 'label', value: 'First' },
      { op: 'setFieldProperty', fieldname: 'a', prop: 'label', value: 'Second' },
    ]
    expect(fieldByName(applyMetaScript(schema, ops), 'a').label).toBe('Second')
  })

  it('no-ops when the target field is absent', () => {
    const out = applyMetaScript(schema, [
      { op: 'setFieldProperty', fieldname: 'missing', prop: 'label', value: 'X' },
      { op: 'addField', after: 'missing', field: { fieldname: 'z', fieldtype: 'Data' } },
    ])
    expect(fields(out).map((f) => f.fieldname)).toEqual(['a', 'b'])
  })

  it('returns the schema unchanged when there are no ops', () => {
    expect(applyMetaScript(schema, [])).toEqual(schema)
  })

  it('does not mutate the input schema (purity)', () => {
    const before = JSON.parse(JSON.stringify(schema))
    applyMetaScript(schema, [
      { op: 'setFieldProperty', fieldname: 'a', prop: 'label', value: 'Renamed' },
      { op: 'hideField', fieldname: 'b' },
      { op: 'addField', after: 'a', field: { fieldname: 'a2', fieldtype: 'Data' } },
    ])
    expect(schema).toEqual(before)
  })
})
