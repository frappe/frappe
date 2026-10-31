// Which apps' `shell.js` the shell may run, over a faked generated module.
import { describe, expect, it, vi } from 'vitest'
import type { ShellHookContribution } from '../types'

const load = async () => ({ setup: () => {} })

vi.mock('virtual:frappe/contributions', () => ({
  default: {
    doctypes: [],
    pages: [],
    itemTypes: [],
    replacements: [],
    settings: [],
    acts: [],
    shellHooks: [
      { app: 'helpdesk', load },
      { app: 'crm', load },
      { app: 'gameplan', load },
    ] satisfies ShellHookContribution[],
  },
}))

vi.mock('@/recordPage', () => ({ addFileScript: vi.fn() }))

describe('shellHookFiles', () => {
  it("holds each active app's shell.js in the site's app order, and none of an app the site lacks", async () => {
    const { shellHookFiles, registerContributions } = await import('../registry')

    registerContributions(['frappe', 'crm', 'helpdesk'])

    expect(shellHookFiles.map((file) => file.app)).toEqual(['crm', 'helpdesk'])
  })
})
