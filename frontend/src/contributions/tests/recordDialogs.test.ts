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
  return Object.assign(registry.opensInDialog, { body: registry.recordDialogBody })
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

describe('recordDialogBody', () => {
  const component = async () => ({})

  it('is the body of the opt-in that names one, and absent for one that names none', async () => {
    const opensIn = await opens([{ ...todo, component }, { ...todo, doctype: 'Note' }], ['frappe'])
    expect(opensIn.body('ToDo', 'frappe')).toBe(component)
    expect(opensIn.body('Note', 'frappe')).toBeUndefined()
    expect(opensIn.body('Event', 'frappe')).toBeUndefined()
  })

  it('takes the entry that names the app over one that names none', async () => {
    const scoped = async () => ({})
    const opensIn = await opens(
      [{ ...todo, component }, { ...todo, apps: ['crm'], component: scoped }],
      ['frappe', 'crm'],
    )
    expect(opensIn.body('ToDo', 'crm')).toBe(scoped)
    expect(opensIn.body('ToDo', 'frappe')).toBe(component)
  })
})
