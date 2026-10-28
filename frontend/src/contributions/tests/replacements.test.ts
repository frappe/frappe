// Which app's page replaces a doctype's record or list page, over a faked generated module.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReplacementContribution } from '../types'

const fake = vi.hoisted(() => ({ replacements: [] as ReplacementContribution[] }))

vi.mock('virtual:frappe/contributions', () => ({
  default: {
    doctypes: [],
    pages: [],
    itemTypes: [],
    acts: [],
    get replacements() {
      return fake.replacements
    },
  },
}))

vi.mock('@/recordPage', () => ({
  registerRecordPage: vi.fn(),
  withRegisteringSource: vi.fn(),
}))

function page(
  app: string,
  doctype: string,
  key: 'record' | 'list',
  foreign = false,
): ReplacementContribution {
  return { app, doctype, key, foreign, component: async () => ({}) }
}

function scoped(page: ReplacementContribution, apps: string[]) {
  return { ...page, apps }
}

async function load(replacements: ReplacementContribution[], appOrder: string[]) {
  fake.replacements = replacements
  vi.resetModules()
  const registry = await import('../registry')
  await registry.registerContributions(appOrder)
  return registry
}

/** `replacementFor` in the shell of `app`, by default the desk's. */
async function resolve(
  replacements: ReplacementContribution[],
  appOrder: string[],
  app = 'frappe',
) {
  const { replacementFor } = await load(replacements, appOrder)
  return (doctype: string, key: 'record' | 'list') => replacementFor(doctype, key, app)
}

describe('replacementFor', () => {
  let error: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    error = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    error.mockRestore()
  })

  it('returns nothing when no app replaces the page', async () => {
    const replacementFor = await resolve([], ['frappe'])
    expect(replacementFor('ToDo', 'record')).toBeUndefined()
    expect(error).not.toHaveBeenCalled()
  })

  it('gives the last custom/ app in the site order the key', async () => {
    const replacementFor = await resolve(
      [page('hrms', 'Lead', 'record', true), page('helpdesk', 'Lead', 'record', true)],
      ['frappe', 'helpdesk', 'hrms'],
    )
    expect(replacementFor('Lead', 'record')?.app).toBe('hrms')
  })

  it('lets a custom/ app beat the owner, whatever the site order', async () => {
    const replacementFor = await resolve(
      [page('hrms', 'Lead', 'record', true), page('crm', 'Lead', 'record')],
      ['frappe', 'hrms', 'crm'],
    )
    expect(replacementFor('Lead', 'record')?.app).toBe('hrms')
  })

  it('decides record and list separately', async () => {
    const replacementFor = await resolve(
      [page('crm', 'Lead', 'record'), page('hrms', 'Lead', 'list', true)],
      ['frappe', 'crm', 'hrms'],
    )
    expect(replacementFor('Lead', 'record')?.app).toBe('crm')
    expect(replacementFor('Lead', 'list')?.app).toBe('hrms')
    expect(replacementFor('Deal', 'record')).toBeUndefined()
    expect(error).not.toHaveBeenCalled()
  })

  it('ignores an app that is not active on the site', async () => {
    const replacementFor = await resolve(
      [page('crm', 'Lead', 'record'), page('hrms', 'Lead', 'record', true)],
      ['frappe', 'crm'],
    )
    expect(replacementFor('Lead', 'record')?.app).toBe('crm')
    expect(error).not.toHaveBeenCalled()
  })

  it('logs one error naming the doctype, the key, the winner and every loser', async () => {
    const replacementFor = await resolve(
      [
        page('crm', 'Lead', 'record'),
        page('hrms', 'Lead', 'record', true),
        page('helpdesk', 'Lead', 'record', true),
      ],
      ['frappe', 'helpdesk', 'crm', 'hrms'],
    )
    replacementFor('Lead', 'record')
    replacementFor('Lead', 'record')
    expect(error).toHaveBeenCalledOnce()
    expect(error).toHaveBeenCalledWith(
      "[frappe] 3 apps replace the record page of 'Lead': 'hrms' is used and " +
        "'crm', 'helpdesk' ignored.",
    )
  })

  it('applies an entry that names apps only in the apps it names', async () => {
    const { replacementFor } = await load(
      [scoped(page('crm', 'Note', 'list', true), ['crm'])],
      ['frappe', 'erpnext', 'crm'],
    )
    expect(replacementFor('Note', 'list', 'crm')?.app).toBe('crm')
    expect(replacementFor('Note', 'list', 'erpnext')).toBeUndefined()
    expect(replacementFor('Note', 'list', 'frappe')).toBeUndefined()
  })

  it('lets an entry that names the app beat one that names none, whatever the run order', async () => {
    const { replacementFor } = await load(
      [scoped(page('crm', 'Note', 'list', true), ['crm']), page('erpnext', 'Note', 'list', true)],
      ['frappe', 'crm', 'erpnext'],
    )
    expect(replacementFor('Note', 'list', 'crm')?.app).toBe('crm')
    expect(replacementFor('Note', 'list', 'erpnext')?.app).toBe('erpnext')
    expect(replacementFor('Note', 'list', 'frappe')?.app).toBe('erpnext')
    expect(error).not.toHaveBeenCalled()
  })

  it('lets any app name any apps, so one app can give two apps two pages', async () => {
    const { replacementFor } = await load(
      [
        { ...scoped(page('custom', 'Contact', 'record', true), ['crm']), title: 'sales' },
        { ...scoped(page('custom', 'Contact', 'record', true), ['helpdesk']), title: 'support' },
        { ...page('custom', 'Contact', 'record', true), title: 'card' },
      ],
      ['frappe', 'crm', 'helpdesk', 'custom'],
    )
    expect(replacementFor('Contact', 'record', 'crm')?.title).toBe('sales')
    expect(replacementFor('Contact', 'record', 'helpdesk')?.title).toBe('support')
    expect(replacementFor('Contact', 'record', 'frappe')?.title).toBe('card')
    expect(error).not.toHaveBeenCalled()
  })

  it('gives the last of two entries naming one app the key, and logs it in that app only', async () => {
    const { replacementFor } = await load(
      [
        scoped(page('crm', 'Note', 'list', true), ['crm']),
        scoped(page('erpnext', 'Note', 'list', true), ['crm', 'erpnext']),
      ],
      ['frappe', 'crm', 'erpnext'],
    )
    expect(replacementFor('Note', 'list', 'erpnext')?.app).toBe('erpnext')
    expect(error).not.toHaveBeenCalled()

    expect(replacementFor('Note', 'list', 'crm')?.app).toBe('erpnext')
    expect(error).toHaveBeenCalledOnce()
    expect(error).toHaveBeenCalledWith(
      "[frappe] 2 apps replace the list page of 'Note': 'erpnext' is used and 'crm' ignored.",
    )
  })

  it('logs no clash among entries naming no apps in an app that an entry names', async () => {
    const { replacementFor } = await load(
      [
        page('crm', 'Note', 'list', true),
        page('erpnext', 'Note', 'list', true),
        scoped(page('helpdesk', 'Note', 'list', true), ['helpdesk']),
      ],
      ['frappe', 'crm', 'erpnext', 'helpdesk'],
    )
    expect(replacementFor('Note', 'list', 'helpdesk')?.app).toBe('helpdesk')
    expect(error).not.toHaveBeenCalled()
  })

  it('lists the pages that win in the app, for the address checks', async () => {
    const { declaredReplacements } = await load(
      [
        scoped(page('crm', 'Note', 'list', true), ['crm']),
        page('erpnext', 'Report', 'record', true),
      ],
      ['frappe', 'crm', 'erpnext'],
    )
    expect(declaredReplacements('crm').map((c) => c.doctype)).toEqual(['Note', 'Report'])
    expect(declaredReplacements('frappe').map((c) => c.doctype)).toEqual(['Report'])
  })
})
