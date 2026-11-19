// Which apps' `field-actions.js` the record page may import, over a faked generated module.
import { describe, expect, it, vi } from 'vitest'
import type { FieldActionsContribution } from '../types'

const load = async () => ({ default: [] })

vi.mock('virtual:frappe/contributions', () => ({
  default: {
    doctypes: [],
    pages: [],
    itemTypes: [],
    replacements: [],
    settings: [],
    acts: [],
    fieldActions: [
      { app: 'helpdesk', load },
      { app: 'crm', load },
      { app: 'gameplan', load },
    ] satisfies FieldActionsContribution[],
  },
}))

vi.mock('@/recordPage', () => ({ addFileScript: vi.fn() }))

describe('fieldActionFiles', () => {
  it("holds each active app's field-actions.js in the site's app order, and none of an app the site lacks", async () => {
    const { fieldActionFiles, registerContributions } = await import('../registry')

    registerContributions(['frappe', 'crm', 'helpdesk'])

    expect(fieldActionFiles.map((file) => file.app)).toEqual(['crm', 'helpdesk'])
  })
})
