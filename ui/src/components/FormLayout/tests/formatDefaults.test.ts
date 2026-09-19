import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { computed } from 'vue'
import {
  getFormatDefaults,
  resetFormatDefaults,
  setFormatDefaults,
} from '../formatDefaults'
import { DEFAULT_NUMBER_FORMAT, DEFAULT_ROUNDING_METHOD } from '../formatNumber'
import { resetSession, setSession } from '../../../composables/useSession'
import type { Session } from '../../../api'

// The session fetch never runs here: every test either publishes a session or
// leaves the store empty, and `getFormatDefaults` only reads it synchronously.
vi.mock('../../../api', () => ({ getSession: vi.fn() }))

function aSession(defaults: Record<string, unknown>): Session {
  return {
    user: {
      name: 'alice@example.com',
      full_name: 'Alice',
      email: 'alice@example.com',
      user_image: null,
    },
    roles: ['All'],
    lang: 'en',
    timezone: 'Asia/Kolkata',
    defaults,
  }
}

// With no session published, the session read returns nothing and we exercise the
// fallback + override layers cleanly.
describe('getFormatDefaults', () => {
  beforeEach(() => resetSession())
  afterEach(() => resetFormatDefaults())

  it('falls back to lib defaults with no session and no override', () => {
    expect(getFormatDefaults()).toEqual({
      number_format: DEFAULT_NUMBER_FORMAT,
      rounding_method: DEFAULT_ROUNDING_METHOD,
    })
  })

  it('lets an override beat the lib fallback', () => {
    setFormatDefaults({ number_format: '#.###,##', currency: 'EUR' })
    const d = getFormatDefaults()
    expect(d.number_format).toBe('#.###,##')
    expect(d.currency).toBe('EUR')
    // Unspecified keys still fall through to the fallback.
    expect(d.rounding_method).toBe(DEFAULT_ROUNDING_METHOD)
  })

  it('merges successive overrides rather than replacing', () => {
    setFormatDefaults({ number_format: '#.###,##' })
    setFormatDefaults({ currency: 'INR' })
    const d = getFormatDefaults()
    expect(d.number_format).toBe('#.###,##')
    expect(d.currency).toBe('INR')
  })

  it('resetFormatDefaults restores the fallback path', () => {
    setFormatDefaults({ currency: 'GBP' })
    resetFormatDefaults()
    expect(getFormatDefaults().currency).toBeUndefined()
  })

  // The bug this guards: a field's `display` computed resolved formatting via
  // getFormatDefaults() but had no reactive dep on the defaults, so it cached
  // stale values and "didn't change when changed from settings".
  it('a computed reading getFormatDefaults re-evaluates after setFormatDefaults', () => {
    const fmt = computed(() => getFormatDefaults().number_format)
    expect(fmt.value).toBe(DEFAULT_NUMBER_FORMAT)
    setFormatDefaults({ number_format: '#.###,##' })
    expect(fmt.value).toBe('#.###,##') // re-evaluated, not cached
  })
})

describe('getFormatDefaults — session defaults layer', () => {
  beforeEach(() => {
    resetSession()
    setSession(
      aSession({
        number_format: '# ###.##',
        currency: 'JPY',
        currency_precision: '0',
        float_precision: '', // blank session value must NOT clobber a fallback
      })
    )
  })
  afterEach(() => {
    resetFormatDefaults()
    resetSession()
  })

  it("reads framework defaults from the session's defaults", () => {
    const d = getFormatDefaults()
    expect(d.number_format).toBe('# ###.##')
    expect(d.currency).toBe('JPY')
    expect(d.currency_precision).toBe('0')
  })

  it('drops blank session values so the fallback survives', () => {
    expect(getFormatDefaults().float_precision).toBeUndefined()
  })

  it('precedence: override beats session beats fallback', () => {
    setFormatDefaults({ currency: 'USD' })
    const d = getFormatDefaults()
    expect(d.currency).toBe('USD') // override
    expect(d.number_format).toBe('# ###.##') // session (no override)
    expect(d.rounding_method).toBe(DEFAULT_ROUNDING_METHOD) // fallback
  })
})
