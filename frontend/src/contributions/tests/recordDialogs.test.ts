// Which doctypes open their records in the record dialog, over a faked generated module.
import { describe, expect, it, vi } from 'vitest'
import type { RecordDialogContribution } from '../types'

const fake = vi.hoisted(() => ({ recordDialogs: [] as RecordDialogContribution[] }))

vi.mock('virtual:frappe/contributions', () => ({
  default: {
    doctypes: [],
    pages: [],
    itemTypes: [],
    acts: [],
    replacements: [],
    get recordDialogs() {
      return fake.recordDialogs
    },
  },
}))

vi.mock('@/recordPage', () => ({
  registerRecordPage: vi.fn(),
  withRegisteringSource: vi.fn(),
}))

async function opens(recordDialogs: RecordDialogContribution[], appOrder: string[]) {
  fake.recordDialogs = recordDialogs
  vi.resetModules()
  const registry = await import('../registry')
  await registry.registerContributions(appOrder)
  return registry.opensInDialog
}

const todo = { app: 'frappe', doctype: 'ToDo', foreign: false }

describe('opensInDialog', () => {
  it('is true for an opted-in doctype and false for the rest', async () => {
    const opensIn = await opens([todo], ['frappe'])
    expect(opensIn('ToDo', 'frappe')).toBe(true)
    expect(opensIn('Note', 'frappe')).toBe(false)
  })

  it('ignores an app that is not active', async () => {
    const opensIn = await opens([{ ...todo, app: 'crm' }], ['frappe'])
    expect(opensIn('ToDo', 'frappe')).toBe(false)
  })

  it('applies a scoped entry only in its apps', async () => {
    const opensIn = await opens([{ ...todo, apps: ['crm'] }], ['frappe', 'crm'])
    expect(opensIn('ToDo', 'crm')).toBe(true)
    expect(opensIn('ToDo', 'frappe')).toBe(false)
    expect(opensIn('ToDo', null)).toBe(false)
  })
})
