import { describe, expect, it } from 'vitest'
import {
  formatJsonFieldValue,
  paramsToRows,
  parseJsonFieldInput,
  rowsToParams,
} from '../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowParams'

describe('workflow JSON fields', () => {
  it('parses complete JSON for action params', () => {
    expect(parseJsonFieldInput('{"status":"Junk"}')).toEqual({
      status: 'Junk',
    })
  })

  it('preserves incomplete JSON while the user edits it', () => {
    const input = '{\n  "status": "Junk"\n'
    const stored = JSON.stringify({ values: parseJsonFieldInput(input) })
    const value = JSON.parse(stored).values

    expect(formatJsonFieldValue(value)).toBe(input)
  })

  it('allows a JSON field to be cleared', () => {
    expect(parseJsonFieldInput('')).toBe('')
  })
})

describe('field/value rows', () => {
  it('reads a legacy single field/value pair as one row', () => {
    expect(paramsToRows({ field: 'status', value: 'Junk' })).toEqual([
      { field: 'status', value: 'Junk' },
    ])
  })

  it('reads a values map as one row per field', () => {
    const params = { values: { status: 'Junk', lost_reason: 'Spam' } }

    expect(paramsToRows(params)).toEqual([
      { field: 'status', value: 'Junk' },
      { field: 'lost_reason', value: 'Spam' },
    ])
  })

  it('keeps the single pair first when both are stored', () => {
    const params = {
      field: 'status',
      value: 'Junk',
      values: { lost_reason: 'Spam' },
    }

    expect(paramsToRows(params)).toEqual([
      { field: 'status', value: 'Junk' },
      { field: 'lost_reason', value: 'Spam' },
    ])
  })

  it('offers one empty row when nothing is set yet', () => {
    expect(paramsToRows({})).toEqual([{ field: '', value: '' }])
  })

  it('writes every row into the values map', () => {
    const rows = [
      { field: 'status', value: 'Junk' },
      { field: 'lost_reason', value: 'Spam' },
    ]

    expect(rowsToParams(rows)).toEqual({
      field: null,
      value: null,
      values: { status: 'Junk', lost_reason: 'Spam' },
    })
  })

  it('drops rows with no field chosen', () => {
    const rows = [
      { field: 'status', value: 'Junk' },
      { field: '', value: 'orphan' },
    ]

    expect(rowsToParams(rows).values).toEqual({ status: 'Junk' })
  })
})
