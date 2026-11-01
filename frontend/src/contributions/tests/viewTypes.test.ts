// Which app's renderer each view type gets, over a faked generated module.
import { describe, expect, it, vi } from 'vitest'
import type { ViewTypeContribution } from '../types'

const frappeTable = async () => ({ default: 'frappe table' })
const crmTable = async () => ({ default: 'crm table' })
const cards = async () => ({ default: 'cards' })

vi.mock('virtual:frappe/contributions', () => ({
  default: {
    doctypes: [],
    pages: [],
    itemTypes: [],
    replacements: [],
    settings: [],
    acts: [],
    viewTypes: [
      { app: 'crm', type: 'Table', renderer: crmTable },
      { app: 'frappe', type: 'Table', renderer: frappeTable },
      { app: 'frappe', type: 'List', renderer: undefined as unknown as () => Promise<unknown> },
      { app: 'myapp', type: 'Cards', renderer: cards },
      { app: 'myapp', type: 'Wall', renderer: undefined as unknown as () => Promise<unknown> },
    ] satisfies ViewTypeContribution[],
  },
}))

vi.mock('@/recordPage', () => ({ addFileScript: vi.fn() }))

describe('viewRenderers', () => {
  it("holds one renderer per type, the first app's in the site's order, and logs the other", async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { viewRenderers, registerContributions } = await import('../registry')

    registerContributions(['frappe', 'crm', 'myapp'])

    expect(viewRenderers).toEqual({ Table: frappeTable, Cards: cards })
    expect(error).toHaveBeenCalledWith(
      "[frappe] two apps ship a renderer for view type 'Table': 'frappe' is used and 'crm' is ignored.",
    )
    expect(viewRenderers).not.toHaveProperty('List')
    expect(error).not.toHaveBeenCalledWith(expect.stringContaining("view type 'List'"))
    expect(error).toHaveBeenCalledWith(
      "[frappe] myapp's view.js for view type 'Wall' exports no renderer; it is ignored.",
    )
  })
})
