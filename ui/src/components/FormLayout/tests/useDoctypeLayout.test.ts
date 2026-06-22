import { beforeEach, describe, expect, it, vi } from 'vitest'

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

// Each created resource reports its meta as already fetched, with one field so
// a successful build is observable.
createResourceMock.mockImplementation((options: any) => ({
  data: {
    docs: [
      {
        name: options.params.doctype,
        fields: [{ fieldname: 'subject', fieldtype: 'Data' }],
      },
    ],
  },
  fetched: false,
  loading: false,
  error: null,
  fetch: fetchMock,
  reload: reloadMock,
}))

import { useDoctypeLayout } from '../useDoctypeLayout'

describe('useDoctypeLayout memoization', () => {
  beforeEach(() => {
    vi.clearAllMocks() // reset call counts; keeps the implementation above
  })

  it('returns the same instance and fetches only once per doctype', () => {
    const a = useDoctypeLayout('Memo Same')
    const b = useDoctypeLayout('Memo Same')

    expect(b).toBe(a)
    expect(createResourceMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('builds the layout from the resolved meta', () => {
    const { layout, error } = useDoctypeLayout('Memo Build')

    expect(error.value).toBeNull()
    expect(layout.value).toHaveLength(1)
    expect(
      layout.value[0].sections[0].columns[0].fields.map((f) => f.fieldname),
    ).toEqual(['subject'])
  })

  it('creates a separate cached resource per doctype', () => {
    const a = useDoctypeLayout('Memo A')
    const b = useDoctypeLayout('Memo B')

    expect(b).not.toBe(a)
    expect(createResourceMock).toHaveBeenCalledTimes(2)

    // A repeat call for an already-cached doctype does not fetch again.
    const aAgain = useDoctypeLayout('Memo A')
    expect(aAgain).toBe(a)
    expect(createResourceMock).toHaveBeenCalledTimes(2)
  })

  it('reload() refreshes the underlying resource', () => {
    const { reload } = useDoctypeLayout('Memo Reload')
    reload()
    expect(reloadMock).toHaveBeenCalledTimes(1)
  })
})
