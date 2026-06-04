import { describe, expect, it } from 'vitest'
import { evaluateDependsOn } from '../dependsOn'

describe('evaluateDependsOn', () => {
  it('treats empty / undefined expressions as no condition (true)', () => {
    expect(evaluateDependsOn(undefined, {})).toBe(true)
    expect(evaluateDependsOn('', {})).toBe(true)
  })

  it('evaluates a bare fieldname by truthiness of doc[fieldname]', () => {
    expect(evaluateDependsOn('status', { status: 'Open' })).toBe(true)
    expect(evaluateDependsOn('status', { status: '' })).toBe(false)
    expect(evaluateDependsOn('status', {})).toBe(false)
  })

  it('treats arrays as truthy only when non-empty', () => {
    expect(evaluateDependsOn('items', { items: [1] })).toBe(true)
    expect(evaluateDependsOn('items', { items: [] })).toBe(false)
  })

  it('runs eval: expressions against { doc }', () => {
    expect(evaluateDependsOn('eval:doc.qty > 1', { qty: 5 })).toBe(true)
    expect(evaluateDependsOn('eval:doc.qty > 1', { qty: 0 })).toBe(false)
    expect(evaluateDependsOn('eval:doc.status == "Open"', { status: 'Open' })).toBe(true)
  })

  it('fails open (returns true) when an eval: expression throws', () => {
    // `doc.nested` is undefined → accessing `.deep` throws a TypeError.
    expect(evaluateDependsOn('eval:doc.nested.deep === 1', {})).toBe(true)
  })
})
