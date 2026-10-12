import { describe, expect, it } from "vitest";
import { canMoveInto, moveNode } from "../tree";
import type { ConditionGroup, ConditionNode } from "../types";

type Node = ConditionNode<string>;
type Group = ConditionGroup<string>;

function group(conditions: Node[], conjunction: "and" | "or" = "and"): Group {
  return { conjunction, conditions };
}

/**
 * ```
 * root         A, B, [G: C, D], [H: E, [I: F]]
 * ```
 * Deep enough to drop into a sibling, into a nested group, and back out.
 */
function tree(): Group {
  return group(["A", "B", group(["C", "D"], "or"), group(["E", group(["F"])])]);
}

const DEEP = 9;

/** The group at `path`, for asserting on what a move left behind. */
function at(root: Group, ...path: number[]): Group {
  let node: Node = root;
  for (const index of path) node = (node as Group).conditions[index];
  return node as Group;
}

describe("moveNode", () => {
  it("moves a row into a sibling group", () => {
    // A (root index 0) into G, between C and D.
    const next = moveNode(tree(), [0], [2], 1, DEEP);

    expect(next.conditions[0]).toBe("B");
    expect(at(next, 1).conditions).toEqual(["C", "A", "D"]);
  });

  it("moves a row into a group nested inside a sibling", () => {
    // B into I, which is root -> H(3) -> I(1).
    const next = moveNode(tree(), [1], [3, 1], 0, DEEP);

    expect(next.conditions).toHaveLength(3);
    expect(at(next, 2, 1).conditions).toEqual(["B", "F"]);
  });

  it("moves a row out to an ancestor", () => {
    // F, the only child of I, out to the root's front.
    const next = moveNode(tree(), [3, 1, 0], [], 0, DEEP);

    expect(next.conditions[0]).toBe("F");
    // I is emptied by the move and goes, the way removeNode takes one.
    expect(at(next, 4).conditions).toEqual(["E"]);
  });

  it("leaves the source tree untouched", () => {
    const before = tree();
    moveNode(before, [0], [2], 0, DEEP);
    expect(before).toEqual(tree());
  });

  it("keeps the destination's operator, not the traveller's", () => {
    // A comes from an `and` root into G, which is `or`. G stays `or`.
    const next = moveNode(tree(), [0], [2], 0, DEEP);
    expect(at(next, 1).conjunction).toBe("or");
    expect(next.conjunction).toBe("and");
  });

  describe("a group emptied by the move", () => {
    it("goes, the same way removeNode takes an emptied group", () => {
      const start = group(["A", group(["B"])]);
      const next = moveNode(start, [1, 0], [], 0, DEEP);

      expect(next.conditions).toEqual(["B", "A"]);
    });

    it("cascades, so an emptied parent goes with it", () => {
      const start = group(["A", group([group(["B"])])]);
      const next = moveNode(start, [1, 0, 0], [], 0, DEEP);

      expect(next.conditions).toEqual(["B", "A"]);
    });

    it("never takes the root, which is the empty state", () => {
      const next = moveNode(group(["A"]), [0], [], 0, DEEP);
      expect(next).toEqual(group(["A"]));
    });

    it("is pruned by identity, not by the path it used to have", () => {
      // The row lands in an ancestor, in front of the very group it came from,
      // so the insertion re-points that group before the prune runs. Pruning by
      // the source's original path removes whatever slid into it. Here, the
      // row that was just dropped.
      const start = group([group(["A"]), "B"]);
      const next = moveNode(start, [0, 0], [], 0, DEEP);

      expect(next.conditions).toEqual(["A", "B"]);
    });
  });

  describe("indices", () => {
    it("appends for a drop past the end", () => {
      const next = moveNode(tree(), [0], [2], 99, DEEP);
      expect(at(next, 1).conditions).toEqual(["C", "D", "A"]);
    });

    it("reorders within one group, which is the same edit", () => {
      const next = moveNode(tree(), [0], [], 1, DEEP);
      expect(next.conditions.slice(0, 2)).toEqual(["B", "A"]);
      expect(next.conditions).toHaveLength(4);
    });
  });

  describe("a reorder, which is a move into the group it is already in", () => {
    /** `A or B or C`, flat. */
    function flat(): Group {
      return group(["A", "B", "C"], "or");
    }

    it("reorders a row within its group", () => {
      expect(moveNode(flat(), [2], [], 0, DEEP).conditions).toEqual([
        "C",
        "A",
        "B",
      ]);
    });

    it("cannot change what the level matches", () => {
      // One operator for the group, so there is no gap for a move to re-point:
      // every arrangement of `A or B or C` is still `A or B or C`.
      for (const [from, to] of [
        [0, 1],
        [0, 2],
        [1, 0],
        [1, 2],
        [2, 0],
        [2, 1],
      ]) {
        const next = moveNode(flat(), [from], [], to, DEEP);
        expect(next.conjunction).toBe("or");
        expect(next.conditions).toHaveLength(3);
      }
    });

    it("moves inside a nested group without touching its parent", () => {
      const next = moveNode(tree(), [2, 1], [2], 0, DEEP);
      expect(at(next, 2).conditions).toEqual(["D", "C"]);
      expect(at(next, 2).conjunction).toBe("or");
      expect(next.conditions[0]).toBe("A");
      expect(next.conditions).toHaveLength(4);
    });

    it("is a no-op when the row does not move", () => {
      expect(moveNode(flat(), [1], [], 1, DEEP)).toEqual(flat());
    });

    it("appends for an index past the end, rather than refusing it", () => {
      // The reparent rule, applied here too: one function, one answer. The row
      // menu never asks for one, since it guards the last row itself.
      expect(moveNode(flat(), [0], [], 3, DEEP).conditions).toEqual([
        "B",
        "C",
        "A",
      ]);
    });

    it("is a no-op for a row that is not there", () => {
      expect(moveNode(flat(), [-1], [], 0, DEEP)).toEqual(flat());
      expect(moveNode(flat(), [9], [], 0, DEEP)).toEqual(flat());
    });

    it("is not refused on depth, since it changes no node's depth", () => {
      // maxDepth 0 forbids every group, and the tree already breaks it. The
      // rows inside stay rearrangeable rather than freezing where they sit.
      expect(moveNode(tree(), [2, 1], [2], 0, 0).conditions).toHaveLength(4);
      expect(at(moveNode(tree(), [2, 1], [2], 0, 0), 2).conditions).toEqual([
        "D",
        "C",
      ]);
    });
  });

  describe("refusals", () => {
    it("refuses a drop that would nest past maxDepth", () => {
      // G is a group at depth 1; dropping it into H (depth 1) would put it at
      // depth 2, and its own contents no deeper. maxDepth 1 refuses it.
      expect(moveNode(tree(), [2], [3], 0, 1)).toEqual(tree());
      // The same move fits under maxDepth 2.
      expect(moveNode(tree(), [2], [3], 0, 2)).not.toEqual(tree());
    });

    it("counts the whole subtree, not just the node that was grabbed", () => {
      // H is a group holding a group, so it is two levels deep. Landing it in G
      // (depth 1) puts its own nested group at depth 3.
      expect(moveNode(tree(), [3], [2], 0, 2)).toEqual(tree());
      expect(moveNode(tree(), [3], [2], 0, 3)).not.toEqual(tree());
    });

    it("never refuses a leaf on depth, since a leaf adds no level", () => {
      expect(canMoveInto(tree(), [0], [3, 1], 2)).toBe(true);
    });

    it("refuses a group dropped into itself or into its own contents", () => {
      expect(moveNode(tree(), [3], [3], 0, DEEP)).toEqual(tree());
      expect(moveNode(tree(), [3], [3, 1], 0, DEEP)).toEqual(tree());
    });

    it("refuses to move the root", () => {
      expect(moveNode(tree(), [], [2], 0, DEEP)).toEqual(tree());
    });

    it("refuses a path that names nothing, or a destination that is a leaf", () => {
      expect(moveNode(tree(), [9], [2], 0, DEEP)).toEqual(tree());
      expect(moveNode(tree(), [0], [9], 0, DEEP)).toEqual(tree());
      expect(moveNode(tree(), [0], [1], 0, DEEP)).toEqual(tree());
    });
  });
});

describe("canMoveInto", () => {
  it("agrees with what the move actually does", () => {
    const cases: Array<[number[], number[], number]> = [
      [[0], [2], DEEP],
      [[3], [2], 2],
      [[3], [3, 1], DEEP],
      [[], [2], DEEP],
      [[9], [2], DEEP],
      [[0], [1], DEEP],
    ];

    for (const [from, to, maxDepth] of cases) {
      const refused = moveNode(tree(), from, to, 0, maxDepth);
      expect(canMoveInto(tree(), from, to, maxDepth)).toBe(
        JSON.stringify(refused) !== JSON.stringify(tree())
      );
    }
  });
});
