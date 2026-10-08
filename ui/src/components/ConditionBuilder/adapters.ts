// Reading and writing Frappe's interleaved condition array. The operator table
// lives in `internal/operators`, the Python compiler in `internal/compile`;
// this module is what a host imports, so both are re-exported through it.
import { emptyTree, isGroup } from "./tree";
import { READ_OPERATOR } from "./internal/operators";
import { compileEntries, foldEntries } from "./internal/compile";
import type {
  ConditionExpressionOptions,
  ConditionGroup,
  ConditionNode,
  ConditionValue,
  FieldConditionValue,
} from "./types";

type Leaf = FieldConditionValue;
type Node = ConditionNode<Leaf>;

export { emptyTree, isGroup, setGroupConjunction } from "./tree";
export { conditionOperators } from "./internal/operators";
export type { ConditionExpressionOptions } from "./types";

/**
 * Convert a tree to the interleaved array Assignment Rule and SLA persist. The
 * format carries a token per gap, so the group's one token is repeated between
 * every surviving pair.
 */
export function toFrappeConditions(tree: ConditionGroup<Leaf>): unknown[] {
  const out: unknown[] = [];
  let written = 0;

  tree.conditions.forEach((node) => {
    // A row with no field holds no condition, so dropping it is lossless.
    if (!isGroup(node) && !node.fieldname) return;

    const encoded = nodeToFrappe(node);

    // A group encoding to nothing is dropped rather than written as `[]`, which
    // the host's compiler would destructure.
    if (isGroup(node) && Array.isArray(encoded) && encoded.length === 0) return;

    // `written`, not the index, so a skipped entry cannot leave the array
    // starting on a conjunction.
    if (written > 0) out.push(tree.conjunction ?? "and");
    out.push(encoded);
    written += 1;
  });

  return out;
}

/**
 * Compile a tree into the Python expression `safe_eval` runs. Goes through
 * `toFrappeConditions`, so a row with no field is dropped exactly as it is on
 * save.
 */
export function toConditionExpression(
  tree: ConditionGroup<Leaf>,
  options: ConditionExpressionOptions = {}
): string {
  return compileEntries(toFrappeConditions(tree), options);
}

/**
 * Parse the array back into a tree, dropping any entry it cannot model. **Lossy
 * on a mixed record:** the array carries a token per gap, a group one per
 * level, so `A and B or C` loads and re-saves as `A and B and C`.
 */
export function fromFrappeConditions(
  conditions: unknown
): ConditionGroup<Leaf> {
  if (!Array.isArray(conditions) || conditions.length === 0) {
    return emptyTree<Leaf>();
  }

  const { items, separators } = foldEntries(conditions, frappeToNode);
  return { conjunction: separators[0] ?? "and", conditions: items };
}

// Helpers

function nodeToFrappe(node: Node): unknown {
  if (isGroup(node)) return toFrappeConditions(node);
  return [node.fieldname, node.operator, node.value];
}

/** A node, or null for an entry this parser cannot model. */
function frappeToNode(item: unknown): Node | null {
  if (Array.isArray(item)) {
    // A new, still-empty group is persisted as `[]`.
    if (item.length === 0) return emptyTree<Leaf>();

    // A group's first element is itself an array; a leaf's is a fieldname.
    if (Array.isArray(item[0])) return fromFrappeConditions(item);
  }

  if (Array.isArray(item) && item.length === 3 && typeof item[0] === "string") {
    const token = String(item[1]).toLowerCase();
    // `hasOwn`, not a bare index: a stored operator named `constructor` would
    // otherwise resolve through `Object.prototype`.
    const operator = Object.hasOwn(READ_OPERATOR, token)
      ? READ_OPERATOR[token]
      : undefined;
    if (operator) {
      return {
        fieldname: item[0],
        operator,
        value: item[2] as ConditionValue,
      };
    }
  }

  return null;
}
