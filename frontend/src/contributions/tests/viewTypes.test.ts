// Which app's renderer each view type gets, over a faked generated module.
import { describe, expect, it, vi } from 'vitest'
import type { ViewTypeContribution } from '../types'

const frappeList = async () => ({ default: 'frappe list' })
const crmList = async () => ({ default: 'crm list' })
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
      { app: 'crm', type: 'List', renderer: crmList },
      { app: 'frappe', type: 'List', renderer: frappeList },
      { app: 'myapp', type: 'Cards', renderer: cards },
    ] satisfies ViewTypeContribution[],
  },
}))

vi.mock('@/recordPage', () => ({ addFileScript: vi.fn() }))

describe('viewRenderers', () => {
  it("holds one renderer per type, the first app's in the site's order, and logs the other", async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { viewRenderers, registerContributions } = await import('../registry')

    registerContributions(['frappe', 'crm', 'myapp'])

    expect(viewRenderers).toEqual({ List: frappeList, Cards: cards })
    expect(error).toHaveBeenCalledWith(
      "[frappe] two apps ship a renderer for view type 'List': 'frappe' is used and 'crm' is ignored.",
    )
  })
})
