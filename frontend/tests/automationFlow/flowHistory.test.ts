import { describe, expect, it } from 'vitest'
import { FlowHistory } from '../../../frappe/automation/doctype/automation_flow/frontend/flow/FlowHistory'

describe('flow history', () => {
  it('undoes and redoes whole snapshots', () => {
    const history = new FlowHistory({ burstMs: 0 })
    history.record('a', 1)
    history.record('b', 2)

    expect(history.undo('c')).toBe('b')
    expect(history.undo('b')).toBe('a')
    expect(history.undo('a')).toBeNull()
    expect(history.redo('a')).toBe('b')
    expect(history.canRedo).toBe(true)
  })

  it('shares one undo step between edits in a burst', () => {
    const history = new FlowHistory({ burstMs: 600 })
    history.record('a', 1000)
    history.record('ab', 1200)
    history.record('abc', 1300)

    expect(history.undo('abcd')).toBe('a')
    expect(history.canUndo).toBe(false)
  })

  it('starts a new step after a pause, and drops redo on a new edit', () => {
    const history = new FlowHistory({ burstMs: 600 })
    history.record('a', 1000)
    history.record('b', 2000)
    history.undo('c')
    history.record('x', 3000)

    expect(history.canRedo).toBe(false)
    expect(history.undo('y')).toBe('x')
  })

  it('keeps at most `limit` steps', () => {
    const history = new FlowHistory({ burstMs: 0, limit: 2 })
    ;['a', 'b', 'c'].forEach((snapshot, at) => history.record(snapshot, at + 1))

    expect(history.undos).toEqual(['b', 'c'])
  })
})
