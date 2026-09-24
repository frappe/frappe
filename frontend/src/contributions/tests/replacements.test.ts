// Which app's page replaces a doctype's record or list page, over a faked generated module.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReplacementContribution } from '../types'

const fake = vi.hoisted(() => ({ replacements: [] as ReplacementContribution[] }))

vi.mock('virtual:frappe/contributions', () => ({
  default: {
    doctypes: [],
    pages: [],
    itemTypes: [],
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

async function resolve(replacements: ReplacementContribution[], appOrder: string[]) {
  fake.replacements = replacements
  vi.resetModules()
  const registry = await import('../registry')
  await registry.registerContributions(appOrder)
  return registry.replacementFor
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

  it('gives the last owner in the site order the key', async () => {
    const replacementFor = await resolve(
      [page('crm', 'Lead', 'record'), page('helpdesk', 'Lead', 'record')],
      ['frappe', 'helpdesk', 'crm'],
    )
    expect(replacementFor('Lead', 'record')?.app).toBe('crm')
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
    await resolve(
      [
        page('crm', 'Lead', 'record'),
        page('hrms', 'Lead', 'record', true),
        page('helpdesk', 'Lead', 'record', true),
      ],
      ['frappe', 'helpdesk', 'crm', 'hrms'],
    )
    expect(error).toHaveBeenCalledOnce()
    expect(error).toHaveBeenCalledWith(
      "[frappe] 3 apps replace the record page of 'Lead': 'hrms' is used and " +
        "'crm', 'helpdesk' ignored.",
    )
  })
})
