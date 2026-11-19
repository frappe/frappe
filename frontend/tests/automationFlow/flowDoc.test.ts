import { describe, expect, it } from 'vitest'
import {
  fromServer,
  keepStepIds,
  copySource,
  newFlow,
  openingFlow,
  savedKey,
  toPayload,
} from '../../../frappe/automation/doctype/automation_flow/frontend/flow/flowDoc'
import { saveErrors } from '../../../frappe/automation/doctype/automation_flow/frontend/flow/flowErrors'
import { newStep } from '../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowSteps'

const row = (idx: number, extra = {}) => ({
  name: `row-${idx}`,
  idx,
  step_type: 'Action',
  action_type: 'SetFieldValue',
  step_key: `step_${idx}`,
  params: '{}',
  parent_step: 0,
  branch: '',
  ...extra,
})

describe('flow document', () => {
  it('reads rows into a tree and writes the same rows back', () => {
    const rows = [row(1), row(2)]
    const doc = fromServer({ name: 'AUTO-00001', actions: rows })

    expect(toPayload(doc).actions.map((r: any) => r.name)).toEqual(['row-1', 'row-2'])
  })

  it('keeps a parsed JSON column as text', () => {
    const doc = fromServer({ name: 'A', actions: [row(1, { params: { field: 'status' } })] })

    expect(doc.actions[0].params).toBe('{"field":"status"}')
  })

  it('is unsaved only when the saved rows would differ', () => {
    const doc = fromServer({ name: 'A', title: 'T', actions: [row(1)] })
    const saved = savedKey(doc)
    doc.actions.push(newStep())
    expect(savedKey(doc)).not.toBe(saved)
    doc.actions.pop()
    expect(savedKey(doc)).toBe(saved)
  })

  it('starts a new flow without a DocType or trigger', () => {
    const flow = newFlow()

    expect(flow.document_type).toBe('')
    expect(flow.trigger_type).toBe('')
    expect(flow.actions).toEqual([])
  })

  it('hands step ids to the tree a save answered with', () => {
    const before = fromServer({ actions: [row(1), row(2)] })
    const after = fromServer({ actions: [row(1), row(2)] })
    keepStepIds(before.actions, after.actions)

    expect(after.actions.map((s: any) => s._id)).toEqual(before.actions.map((s: any) => s._id))
  })
})

describe('refused saves', () => {
  it('points a field error of a row at the step in that row', () => {
    const tree = fromServer({ actions: [row(1), row(2)] }).actions
    const { errors, general } = saveErrors(
      Object.assign(new Error('Row 2: Parameter value is required'), {
        fieldErrors: [
          { fieldname: 'params', parentfield: 'actions', idx: 2, message: 'Parameter value is required' },
        ],
      }),
      tree,
    )

    expect(errors[tree[1]._id]).toEqual(['Parameter value is required'])
    expect(general).toBe('')
  })

  it('counts an outcome row a wait gains on save', () => {
    const wait = newStep({ step_type: 'WaitForEvent' })
    wait.children.If.push(newStep())
    const { errors } = saveErrors(
      Object.assign(new Error('Row 3: broken'), {
        fieldErrors: [{ fieldname: 'params', parentfield: 'actions', idx: 3, message: 'broken' }],
      }),
      [wait],
    )

    expect(Object.keys(errors)).toEqual([wait.children.If[0]._id])
  })

  it('ignores the words of a message: only the row index maps it', () => {
    const tree = fromServer({ actions: [row(1), row(2)] }).actions
    const { errors, general } = saveErrors(new Error('Zeile 2: Wert fehlt'), tree)

    expect(errors).toEqual({})
    expect(general).toBe('Zeile 2: Wert fehlt')
  })

  it('keeps a message with no row for the flow, and field errors for the trigger', () => {
    const tree = fromServer({ actions: [row(1)] }).actions
    const plain = saveErrors(new Error('Enable only after adding an action'), tree)
    const field = saveErrors(
      Object.assign(new Error('x'), {
        fieldErrors: [{ fieldname: 'trigger_type', message: 'Required' }],
      }),
      tree,
    )

    expect(plain.general).toBe('Enable only after adding an action')
    expect(field.errors.trigger).toEqual(['Required'])
  })
})

describe('openingFlow', () => {
  it('names the flow to copy from the first __copy_of value', () => {
    expect(copySource({ __copy_of: 'AUTO-1' })).toBe('AUTO-1')
    expect(copySource({ __copy_of: ['AUTO-2', 'AUTO-3'] })).toBe('AUTO-2')
    expect(copySource({})).toBeNull()
  })

  it('is the empty flow with no copy', () => {
    expect(openingFlow(null)).toEqual(newFlow())
  })

  it('folds a copy into the tree and keeps it nameless', () => {
    const flow = openingFlow({ title: 'A', document_type: 'ToDo', actions: [row(1)] })
    expect(flow.name).toBeUndefined()
    expect(flow.actions).toHaveLength(1)
  })

  it('lays the address values over the copy, enabled as a number', () => {
    const flow = openingFlow({ title: 'A', enabled: 1 }, { title: 'B', enabled: '0', other: 'x' })
    expect([flow.title, flow.enabled, flow.other]).toEqual(['B', 0, undefined])
  })
})
