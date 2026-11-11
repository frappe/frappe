import { describe, expect, it, vi } from 'vitest'

// workflowCapabilities calls the server; the graph tests need only its lookups.
vi.mock(
  '../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowCapabilities',
  () => ({ actionSchema: () => null, capabilitiesFor: () => null }),
)
import { workflowEdges } from '../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowEdges'
import { workflowNodes } from '../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowGraph'
import { newStep } from '../../../frappe/automation/doctype/automation_flow/frontend/flow/workflowSteps'

describe('workflow graph connectors', () => {
  it('converges both condition branches into the following step', () => {
    const condition = newStep({ step_type: 'If' })
    const trueAction = newStep()
    const falseAction = newStep()
    const joinedStep = newStep({ step_type: 'Wait' })
    condition.children.If.push(trueAction)
    condition.children.Else.push(falseAction)

    const edges = workflowEdges([condition, joinedStep])

    expect(
      edges.map(({ source, target, label }) => [source, target, label]),
    ).toEqual([
      ['trigger', condition._id, null],
      [condition._id, trueAction._id, 'True'],
      [condition._id, falseAction._id, 'False'],
      [trueAction._id, joinedStep._id, null],
      [falseAction._id, joinedStep._id, null],
    ])
  })
})

describe('continuing past a condition', () => {
  const branchNode = (doc) =>
    workflowNodes(doc).find((node) => node.data.branching)

  it('withholds the after-branches button while an arm is empty', () => {
    const condition = newStep({ step_type: 'If' })
    condition.children.If.push(newStep())

    const node = branchNode({ actions: [condition] })

    expect(node.data.canContinue).toBe(false)
    expect(node.data.arms.map((arm) => arm.key)).toEqual(['Else'])
  })

  it('offers it once both arms lead somewhere', () => {
    const condition = newStep({ step_type: 'If' })
    condition.children.If.push(newStep())
    condition.children.Else.push(newStep())

    const node = branchNode({ actions: [condition] })

    expect(node.data.canContinue).toBe(true)
    expect(node.data.arms).toEqual([])
  })
})
