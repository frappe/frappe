import { describe, expect, it } from "vitest";
import { removeNode } from "../tree";
import type { ConditionGroup } from "../types";

/** `A and (B and (C))`, deep enough for a cascade to have somewhere to go. */
function nested(): ConditionGroup<string> {
  return {
    conjunction: "and",
    conditions: [
      "A",
      {
        conjunction: "and",
        conditions: ["B", { conjunction: "or", conditions: ["C"] }],
      },
    ],
  };
}

describe("removeNode", () => {
  it("takes a row and leaves its siblings", () => {
    const next = removeNode(
      { conjunction: "and", conditions: ["A", "B", "C"] },
      [1]
    );
    expect(next.conditions).toEqual(["A", "C"]);
  });

  it("takes the group a row leaves empty", () => {
    // C is the only child of the innermost group, so that group goes too.
    const next = removeNode(nested(), [1, 1, 0]);
    expect(next).toEqual({
      conjunction: "and",
      conditions: ["A", { conjunction: "and", conditions: ["B"] }],
    });
  });

  it("cascades past more than one level", () => {
    const tree: ConditionGroup<string> = {
      conjunction: "and",
      conditions: [
        "A",
        {
          conjunction: "and",
          conditions: [{ conjunction: "or", conditions: ["B"] }],
        },
      ],
    };
    // Removing B empties its group, which empties the group holding that.
    const next = removeNode(tree, [1, 0, 0]);
    expect(next).toEqual({ conjunction: "and", conditions: ["A"] });
  });

  it("never takes the root, however empty it gets", () => {
    const next = removeNode({ conjunction: "and", conditions: ["A"] }, [0]);
    expect(next).toEqual({ conjunction: "and", conditions: [] });
  });

  it("leaves a group that still holds something", () => {
    const next = removeNode(nested(), [1, 0]);
    expect(next.conditions[1]).toEqual({
      conjunction: "and",
      conditions: [{ conjunction: "or", conditions: ["C"] }],
    });
  });

  it("empties the tree when the root itself is named", () => {
    const next = removeNode(nested(), []);
    expect(next.conditions).toEqual([]);
  });

  it("does not touch the tree it was handed", () => {
    const before = nested();
    removeNode(before, [1, 1, 0]);
    expect(before).toEqual(nested());
  });

  it("is a no-op on a path that resolves to nothing", () => {
    const next = removeNode(nested(), [9, 9]);
    expect(next).toEqual(nested());
  });
});
