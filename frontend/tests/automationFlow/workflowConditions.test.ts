import { describe, expect, it } from 'vitest'
import {
  isFilterExpression,
  summarizeCondition,
  toExpression,
  toFilters,
} from '../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowConditions'

const fields = [
  { fieldname: 'status', fieldtype: 'Link' },
  { fieldname: 'organization', fieldtype: 'Data' },
  { fieldname: 'job_title', fieldtype: 'Data' },
  { fieldname: 'annual_revenue', fieldtype: 'Currency' },
  { fieldname: 'converted', fieldtype: 'Check' },
]

describe('building a condition from filters', () => {
  it('quotes text and leaves numbers bare', () => {
    expect(toExpression([['status', '=', 'Qualified']], fields)).toBe(
      'doc.status == "Qualified"',
    )
    expect(toExpression([['annual_revenue', '>=', '50000']], fields)).toBe(
      'doc.annual_revenue >= 50000',
    )
  })

  it('writes membership, presence and contains without builtins', () => {
    expect(toExpression([['status', 'in', ['New', 'Open']]], fields)).toBe(
      'doc.status in ["New", "Open"]',
    )
    expect(toExpression([['organization', 'is', 'set']], fields)).toBe(
      '(doc.organization or "") != ""',
    )
    expect(toExpression([['job_title', 'like', '%Head%']], fields)).toBe(
      '"head" in (doc.job_title or "").lower()',
    )
  })

  it('joins every filter with and', () => {
    expect(
      toExpression(
        [
          ['status', '=', 'Qualified'],
          ['converted', '=', 0],
        ],
        fields,
      ),
    ).toBe('doc.status == "Qualified" and doc.converted == 0')
  })

  it('escapes quotes in values', () => {
    expect(toExpression([['organization', '=', 'A "big" co']], fields)).toBe(
      'doc.organization == "A \\"big\\" co"',
    )
  })
})

describe('reading a condition back into filters', () => {
  it('round-trips what it generated, conjunctions included', () => {
    const conditions = [
      ['status', 'in', ['New', 'Open']],
      'and',
      ['job_title', 'not like', 'intern'],
      'or',
      ['organization', 'is', 'not set'],
    ]
    const expression = toExpression(conditions, fields)

    expect(toFilters(expression)).toEqual(conditions)
  })

  it('keeps a group together', () => {
    const conditions = [
      ['status', '=', 'Open'],
      'and',
      [['source', '=', 'Website'], 'or', ['source', '=', 'Referral']],
    ]
    const expression = toExpression(conditions, fields)

    expect(expression).toBe(
      'doc.status == "Open" and (doc.source == "Website" or doc.source == "Referral")',
    )
    expect(toFilters(expression)).toEqual(conditions)
  })

  it('accepts the single quotes a Python-authored condition uses', () => {
    expect(toFilters("doc.status in ['New', 'Open']")).toEqual([
      ['status', 'in', ['New', 'Open']],
    ])
    expect(toFilters("doc.status == 'Qualified'")).toEqual([
      ['status', '=', 'Qualified'],
    ])
  })

  it('refuses anything filters cannot express', () => {
    expect(
      isFilterExpression('doc.email.split("@")[-1] not in ["a.com"]'),
    ).toBe(false)
    expect(
      isFilterExpression('context.get("event", {}).get("x") == "Matched"'),
    ).toBe(false)
    expect(toFilters('doc.status == "Qualified"')).not.toBeNull()
  })

  it('treats an empty condition as no filters', () => {
    expect(toFilters('')).toEqual([])
    expect(isFilterExpression('')).toBe(true)
  })

  it('accepts an empty membership list while a filter row is incomplete', () => {
    expect(toFilters('doc.status in []')).toEqual([['status', 'in', []]])
    expect(toFilters('doc.status not in []')).toEqual([
      ['status', 'not in', []],
    ])
  })
})

describe('refusing expressions it cannot represent', () => {
  const SENIORITY =
    '"chief" in (doc.job_title or "").lower() or "head" in (doc.job_title or "").lower()'
  const TOTAL = '(context["steps"].get("a", {}).get("delta", 0)) >= 45'

  it('reads an or-chain as two contains rows', () => {
    expect(toFilters(SENIORITY)).toEqual([
      ['job_title', 'like', 'chief'],
      'or',
      ['job_title', 'like', 'head'],
    ])
    expect(toExpression(toFilters(SENIORITY), fields)).toBe(SENIORITY)
  })

  it('rejects expressions that are not a plain field comparison', () => {
    expect(toFilters(TOTAL)).toBeNull()
    expect(toFilters('doc.email.split("@")[-1] == "acme.com"')).toBeNull()
    expect(toFilters('doc.status == doc.other')).toBeNull()
  })

  it('still accepts the plain forms it writes', () => {
    expect(toFilters('doc.status == "Open"')).toEqual([['status', '=', 'Open']])
    expect(toFilters('doc.score >= 45')).toEqual([['score', '>=', 45]])
  })
})

describe('summaries', () => {
  it('reads a condition as a sentence', () => {
    expect(summarizeCondition('doc.source == "Website"')).toBe(
      'Source is Website',
    )
    expect(summarizeCondition('(doc.organization or "") != ""')).toBe(
      'Organization is set',
    )
    expect(summarizeCondition('doc.status in ["New", "Open"]')).toBe(
      'Status is one of New, Open',
    )
    expect(summarizeCondition('"head" in (doc.job_title or "").lower()')).toBe(
      'Job title contains head',
    )
  })
})
