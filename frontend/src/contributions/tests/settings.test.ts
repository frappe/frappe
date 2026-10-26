// Which component a settings block names, over a faked generated module.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SettingsComponentContribution } from '../types'

const telephony = async () => ({})

const fake = vi.hoisted(() => ({ settings: [] as SettingsComponentContribution[] }))

vi.mock('virtual:frappe/contributions', () => ({
  default: {
    doctypes: [],
    pages: [],
    itemTypes: [],
    replacements: [],
    get settings() {
      return fake.settings
    },
  },
}))

vi.mock('@/recordPage', () => ({ addFileScript: vi.fn() }))

describe('settingsComponentFor', () => {
  let warn: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    fake.settings = [{ app: 'crm', name: 'telephony', component: telephony }]
    warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    warn.mockRestore()
  })

  it('returns the lazy component the app ships under that name', async () => {
    const { settingsComponentFor } = await import('../registry')

    expect(settingsComponentFor('crm', 'telephony')).toBe(telephony)
    expect(warn).not.toHaveBeenCalled()
  })

  it('drops a block whose file is missing with a warning, and never throws', async () => {
    const { settingsComponentFor } = await import('../registry')

    expect(settingsComponentFor('crm', 'dialer')).toBeUndefined()
    expect(settingsComponentFor('helpdesk', 'telephony')).toBeUndefined()
    expect(warn).toHaveBeenCalledTimes(2)
    expect(warn.mock.calls[0][0]).toContain('crm ships no dialer.vue')
  })
})
