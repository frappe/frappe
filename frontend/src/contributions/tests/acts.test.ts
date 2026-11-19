// Which apps' `acts.js` the shell imports, over a faked generated module.
import { describe, expect, it, vi } from 'vitest'
import type { ActsContribution } from '../types'

const load = async () => ({ default: [] })

vi.mock('virtual:frappe/contributions', () => ({
  default: {
    doctypes: [],
    pages: [],
    itemTypes: [],
    replacements: [],
    settings: [],
    acts: [
      { app: 'helpdesk', load },
      { app: 'crm', load },
      { app: 'gameplan', load },
    ] satisfies ActsContribution[],
  },
}))

vi.mock('@/recordPage', () => ({ addFileScript: vi.fn() }))

describe('actsFiles', () => {
  it("holds each active app's acts.js in the site's app order, and none of an app the site lacks", async () => {
    const { actsFiles, registerContributions } = await import('../registry')

    registerContributions(['frappe', 'crm', 'helpdesk'])

    expect(actsFiles.map((file) => file.app)).toEqual(['crm', 'helpdesk'])
  })
})
