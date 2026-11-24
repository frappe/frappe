import { describe, expect, it } from "vitest";
import {
  EVENT_MATCHED,
  layoutSteps,
  newStep,
  nodeAtRow,
  removeStep,
  stepsBefore,
  setStepType,
  toRows,
  toTree,
} from "../steps";

describe("workflow layout", () => {
  it("places sequential steps left to right on one row", () => {
    const positions = layoutSteps([newStep(), newStep()]).map(
      ({ position }) => position
    );

    expect(positions.map(({ y }) => y)).toEqual([0, 0]);
    expect(positions[1].x).toBeGreaterThan(positions[0].x);
  });

  it("splits condition arms above and below the trunk", () => {
    const condition = newStep({ step_type: "If" });
    condition.children.If.push(newStep());
    condition.children.Else.push(newStep());

    const [branch, ifArm, elseArm] = layoutSteps([condition]).map(
      ({ position }) => position
    );

    expect(branch.y).toBe(0);
    expect(ifArm.y).toBeLessThan(0);
    expect(elseArm.y).toBeGreaterThan(0);
    expect(ifArm.x).toBe(elseArm.x);
    expect(ifArm.x).toBeGreaterThan(branch.x);
  });

  it("gives a wait-for-event step the same two arms", () => {
    const wait = newStep({ step_type: "WaitForEvent" });
    wait.children.If.push(newStep());
    wait.children.Else.push(newStep());

    const [, ifArm, elseArm] = layoutSteps([wait]).map(
      ({ position }) => position
    );

    expect(ifArm.y).toBeLessThan(elseArm.y);
  });
});

describe("step removal", () => {
  it("removes the requested adjacent step by id", () => {
    const first = newStep();
    const selected = newStep();
    const last = newStep();
    const tree = [first, selected, last];

    removeStep(tree, selected._id);

    expect(tree).toEqual([first, last]);
  });

  it("removes the requested nested step by id", () => {
    const condition = newStep({ step_type: "If" });
    const behind = newStep();
    const selected = newStep();
    condition.children.If.push(behind, selected);

    removeStep([condition], selected._id);

    expect(condition.children.If).toEqual([behind]);
  });
});

describe("wait-for-event arms", () => {
  const wait = () =>
    newStep({ step_type: "WaitForEvent", step_key: "wait_for_reply" });

  it("writes the outcome condition the engine expects", () => {
    const node = wait();
    node.children.If.push(newStep({ step_key: "hot" }));
    node.children.Else.push(newStep({ step_key: "cold" }));

    const rows = toRows([node]);

    expect(
      rows.map((row) => [row.idx, row.step_type, row.parent_step, row.branch])
    ).toEqual([
      [1, "WaitForEvent", 0, ""],
      [2, "If", 0, ""],
      [3, "Action", 2, "If"],
      [4, "Action", 2, "Else"],
    ]);
    expect(rows[1].step_condition).toBe(EVENT_MATCHED);
  });

  it("folds that condition back into the wait when reading", () => {
    const tree = toTree([
      { idx: 1, step_type: "WaitForEvent", step_key: "wait_for_reply" },
      {
        idx: 2,
        step_type: "If",
        step_key: "did_reply",
        step_condition: EVENT_MATCHED,
      },
      {
        idx: 3,
        step_type: "Action",
        step_key: "hot",
        parent_step: 2,
        branch: "If",
      },
      {
        idx: 4,
        step_type: "Action",
        step_key: "cold",
        parent_step: 2,
        branch: "Else",
      },
    ]);

    expect(tree).toHaveLength(1);
    expect(tree[0].step_type).toBe("WaitForEvent");
    expect(tree[0].children.If.map((n) => n.step_key)).toEqual(["hot"]);
    expect(tree[0].children.Else.map((n) => n.step_key)).toEqual(["cold"]);
  });

  it("round-trips without renaming the outcome step", () => {
    const rows = [
      { idx: 1, step_type: "WaitForEvent", step_key: "wait_for_reply" },
      {
        idx: 2,
        step_type: "If",
        step_key: "did_reply",
        step_condition: EVENT_MATCHED,
      },
      {
        idx: 3,
        step_type: "Action",
        step_key: "hot",
        parent_step: 2,
        branch: "If",
      },
    ];

    expect(toRows(toTree(rows)).map((row) => row.step_key)).toEqual([
      "wait_for_reply",
      "did_reply",
      "hot",
    ]);
  });

  it("leaves a wait with no arms as a single row", () => {
    expect(toRows([wait()])).toHaveLength(1);
  });

  it("keeps an unrelated If next to a wait untouched", () => {
    const tree = toTree([
      { idx: 1, step_type: "WaitForEvent", step_key: "wait_for_reply" },
      {
        idx: 2,
        step_type: "If",
        step_key: "other",
        step_condition: 'doc.status == "Open"',
      },
    ]);

    expect(tree.map((node) => node.step_type)).toEqual(["WaitForEvent", "If"]);
  });
});

describe("step keys", () => {
  it("names an untitled step after what it does", () => {
    const rows = toRows([
      newStep({ action_type: "AdjustLeadScore" }),
      newStep({ action_type: "AdjustLeadScore" }),
      newStep({ step_type: "If" }),
    ]);

    expect(rows.map((row) => row.step_key)).toEqual([
      "adjust_lead_score",
      "adjust_lead_score_2",
      "condition",
    ]);
  });

  it("never overwrites a key someone chose", () => {
    expect(
      toRows([newStep({ step_key: "mine", action_type: "X" })])[0].step_key
    ).toBe("mine");
  });
});

describe("row to node lookup", () => {
  const wait = (arms) => {
    const node = newStep({ step_type: "WaitForEvent" });
    Object.assign(node.children, arms);
    return node;
  };

  it("matches layout order when no wait has arms", () => {
    const [a, b] = [newStep(), newStep({ step_type: "WaitForEvent" })];
    expect([1, 2].map((i) => nodeAtRow([a, b], i))).toEqual([a, b]);
    expect(nodeAtRow([a, b], 3)).toBeNull();
  });

  it("counts the outcome row a wait with arms gains", () => {
    const [a, b, c, d] = [newStep(), newStep(), newStep(), newStep()];
    const w = wait({ If: [b], Else: [c] });
    const tree = [a, w, d];

    expect(toRows(tree)).toHaveLength(6);
    expect([1, 2, 3, 4, 5, 6].map((i) => nodeAtRow(tree, i))).toEqual([
      a,
      w,
      w,
      b,
      c,
      d,
    ]);
    expect(nodeAtRow(tree, 7)).toBeNull();
  });

  it("finds steps after a wait nested inside an arm", () => {
    const inner = newStep();
    const nested = wait({ If: [inner], Else: [] });
    const condition = newStep({ step_type: "If" });
    condition.children.If.push(nested);
    const after = newStep();
    const tree = [condition, after];

    // If, nested wait, its outcome, inner, after
    expect(nodeAtRow(tree, 4)).toBe(inner);
    expect(nodeAtRow(tree, 5)).toBe(after);
  });
});

describe("available step outputs", () => {
  it("excludes the opposite arm and conditional outputs after a join", () => {
    const before = newStep();
    const condition = newStep({ step_type: "If" });
    const yes = newStep();
    const no = newStep();
    const after = newStep();
    condition.children.If.push(yes);
    condition.children.Else.push(no);
    const tree = [before, condition, after];
    expect(stepsBefore(tree, no)).toEqual([before, condition]);
    expect(stepsBefore(tree, after)).toEqual([before, condition]);
    expect(stepsBefore(tree, newStep())).toEqual([]);
  });

  it("retains earlier steps in the same nested arm", () => {
    const outer = newStep({ step_type: "If" });
    const before = newStep();
    const inner = newStep({ step_type: "If" });
    const target = newStep();
    outer.children.If.push(before, inner);
    inner.children.Else.push(target);
    expect(stepsBefore([outer], target)).toEqual([outer, before, inner]);
  });
});

describe("step type changes", () => {
  it("stores the displayed wait units when changing step types", () => {
    const node = newStep();
    setStepType(node, "Wait");
    expect(JSON.parse(node.params).unit).toBe("Minutes");
    setStepType(node, "WaitForEvent");
    expect(JSON.parse(node.params).timeout_unit).toBe("Days");
  });

  it("retains configured units and clears branches only when applying a nonbranching type", () => {
    const node = newStep({ step_type: "If", params: '{"unit":"Hours"}' });
    const child = newStep();
    node.children.If.push(child);
    setStepType(node, "WaitForEvent");
    expect(node.children.If).toEqual([child]);
    setStepType(node, "Wait");
    expect(JSON.parse(node.params).unit).toBe("Hours");
    expect(node.children).toEqual({ If: [], Else: [] });
  });
});

describe("step identities and outcome preservation", () => {
  it("reserves existing keys even when unnamed steps precede them", () => {
    const unnamed = newStep({ action_type: "SetFieldValue" });
    const named = newStep({ step_key: "set_field_value" });
    expect(toRows([unnamed, named]).map((row) => row.step_key)).toEqual([
      "set_field_value_2",
      "set_field_value",
    ]);
  });

  it("reserves outcome keys and retries generated outcome suffixes", () => {
    const node = newStep({ step_type: "WaitForEvent", step_key: "wait" });
    node.children.If.push(newStep({ step_key: "wait_outcome_2" }));
    const rows = toRows([newStep({ step_key: "wait_outcome" }), node]);
    expect(rows.map((row) => row.step_key)).toEqual([
      "wait_outcome",
      "wait",
      "wait_outcome_3",
      "wait_outcome_2",
    ]);
    const existing = newStep({
      step_type: "WaitForEvent",
      _outcomeKey: "action",
    });
    existing.children.If.push(newStep({ step_key: "child" }));
    expect(toRows([newStep(), existing])[0].step_key).toBe("action_2");
  });

  it("does not fold an outcome If that has additional conditions", () => {
    const rows = [
      { idx: 1, step_type: "WaitForEvent", step_key: "wait" },
      {
        idx: 2,
        step_type: "If",
        step_key: "outcome",
        step_condition: EVENT_MATCHED,
        related_condition: '{"relationship":"todos","operator":"exists"}',
      },
      {
        idx: 3,
        step_type: "Action",
        step_key: "child",
        parent_step: 2,
        branch: "If",
      },
    ];
    const tree = toTree(rows);
    expect(tree).toHaveLength(2);
    expect(toRows(tree)[1].related_condition).toBe(rows[1].related_condition);
  });
});
