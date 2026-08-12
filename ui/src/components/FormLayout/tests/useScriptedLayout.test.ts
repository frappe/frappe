import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

// Hoisted so the factory passed to `vi.mock` can reference them.
const { createResourceMock, fetchMock, reloadMock } = vi.hoisted(() => ({
  createResourceMock: vi.fn(),
  fetchMock: vi.fn(),
  reloadMock: vi.fn(),
}))

vi.mock('frappe-ui', () => ({
  createResource: createResourceMock,
  frappeRequest: vi.fn(),
}))

// Each created resource reports its meta as already fetched, with two fields so
// scripted property/insert/hide changes are observable.
createResourceMock.mockImplementation((options: any) => ({
  data: {
    docs: [
      {
        name: options.params.doctype,
        fields: [
          { fieldname: 'subject', fieldtype: 'Data', label: 'Subject' },
          { fieldname: 'status', fieldtype: 'Select', label: 'Status' },
        ],
      },
    ],
  },
  fetched: false,
  loading: false,
  error: null,
  fetch: fetchMock,
  reload: reloadMock,
}))

import { useScriptedLayout } from '../useScriptedLayout'
import type { MetaOp } from '../applyMetaScript'
import type { FormLayoutSchema } from '../types'

const fields = (layout: FormLayoutSchema) =>
  layout[0].sections[0].columns[0].fields

describe('useScriptedLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('applies static ops onto the doctype layout', () => {
    const ops: MetaOp[] = [
      { op: 'setFieldProperty', fieldname: 'subject', prop: 'label', value: 'Renamed' },
      { op: 'addField', after: 'status', field: { fieldname: 'priority', fieldtype: 'Select' } },
    ]
    const { layout } = useScriptedLayout('Scripted Static', ops)

    expect(fields(layout.value).map((f) => f.fieldname)).toEqual([
      'subject',
      'status',
      'priority',
    ])
    expect(fields(layout.value).find((f) => f.fieldname === 'subject')!.label).toBe('Renamed')
  })

  it('re-runs the transform when reactive ops change', () => {
    const ops = ref<MetaOp[]>([])
    const { layout } = useScriptedLayout('Scripted Reactive', ops)

    expect(fields(layout.value).map((f) => f.fieldname)).toEqual(['subject', 'status'])

    ops.value = [{ op: 'hideField', fieldname: 'status' }]
    expect(fields(layout.value).find((f) => f.fieldname === 'status')!.hidden).toBe(true)
  })

  it('passes through load state and reload from the underlying layout', () => {
    const { loading, error, reload } = useScriptedLayout('Scripted State', [])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
    reload()
    expect(reloadMock).toHaveBeenCalledTimes(1)
  })
})
