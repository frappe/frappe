import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { computed } from 'vue'
import {
  getFormatDefaults,
  resetFormatDefaults,
  setFormatDefaults,
} from '../formatDefaults'
import { DEFAULT_NUMBER_FORMAT, DEFAULT_ROUNDING_METHOD } from '../formatNumber'

// These run in vitest's node env where `window` is undefined — exactly the
// "no window.sysdefaults" condition called out in ui/CLAUDE.md. So the boot read
// returns nothing and we exercise the fallback + override layers cleanly.
describe('getFormatDefaults', () => {
  afterEach(() => resetFormatDefaults())

  it('falls back to lib defaults with no boot and no override', () => {
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

describe('getFormatDefaults — window.sysdefaults (boot) layer', () => {
  beforeEach(() => {
    ;(globalThis as any).window = {
      sysdefaults: {
        number_format: '# ###.##',
        currency: 'JPY',
        currency_precision: '0',
        float_precision: '', // blank boot value must NOT clobber a fallback
      },
    }
  })
  afterEach(() => {
    resetFormatDefaults()
    delete (globalThis as any).window
  })

  it('reads framework defaults from window.sysdefaults', () => {
    const d = getFormatDefaults()
    expect(d.number_format).toBe('# ###.##')
    expect(d.currency).toBe('JPY')
    expect(d.currency_precision).toBe('0')
  })

  it('drops blank boot values so the fallback survives', () => {
    expect(getFormatDefaults().float_precision).toBeUndefined()
  })

  it('precedence: override beats boot beats fallback', () => {
    setFormatDefaults({ currency: 'USD' })
    const d = getFormatDefaults()
    expect(d.currency).toBe('USD') // override
    expect(d.number_format).toBe('# ###.##') // boot (no override)
    expect(d.rounding_method).toBe(DEFAULT_ROUNDING_METHOD) // fallback
  })
})
