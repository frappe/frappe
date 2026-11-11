import { describe, expect, it } from 'vitest'
import {
  fromServer,
  keepStepIds,
  newFlow,
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
  it('points a Row N message at the step in that row', () => {
    const tree = fromServer({ actions: [row(1), row(2)] }).actions
    const { errors, general } = saveErrors(
      new Error('Row 2: Parameter value is required'),
      tree,
    )

    expect(errors[tree[1]._id]).toEqual(['Parameter value is required'])
    expect(general).toBe('')
  })

  it('counts an outcome row a wait gains on save', () => {
    const wait = newStep({ step_type: 'WaitForEvent' })
    wait.children.If.push(newStep())
    const { errors } = saveErrors(new Error('Row 3: broken'), [wait])

    expect(Object.keys(errors)).toEqual([wait.children.If[0]._id])
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
