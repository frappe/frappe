import type {
  ConditionGroup,
  ConditionNode,
  ConditionPath,
  Conjunction,
} from "./types";

// ---------------------------------------------------------------------------
// Reading a tree
// ---------------------------------------------------------------------------

export function isGroup<T>(node: ConditionNode<T>): node is ConditionGroup<T> {
  return (
    node !== null &&
    typeof node === "object" &&
    Array.isArray((node as ConditionGroup<T>).conditions)
  );
}

export function emptyTree<T>(): ConditionGroup<T> {
  return { conjunction: "and", conditions: [] };
}

export function getNode<T>(
  tree: ConditionGroup<T>,
  path: ConditionPath
): ConditionNode<T> | undefined {
  let node: ConditionNode<T> = tree;
  for (const index of path) {
    if (!isGroup(node)) return undefined;
    node = node.conditions[index];
    if (node === undefined) return undefined;
  }
  return node;
}

/** How many conditions the tree holds, at any depth. Groups are not counted. */
export function countConditions<T>(group: ConditionGroup<T>): number {
  return group.conditions.reduce<number>(
    (total, node) => total + (isGroup(node) ? countConditions(node) : 1),
    0
  );
}

/**
 * How many groups the tree holds below the root. Comparing the count before and
 * after is the only way to know a removal cascaded: a sibling shifts into the
 * pruned index.
 */
export function countGroups<T>(group: ConditionGroup<T>): number {
  return group.conditions.reduce<number>(
    (total, node) => total + (isGroup(node) ? 1 + countGroups(node) : 0),
    0
  );
}

/** Whether two paths address the same node. */
export function samePath(a: ConditionPath, b: ConditionPath): boolean {
  return a.length === b.length && a.every((index, depth) => index === b[depth]);
}

export function canNest(groupPath: ConditionPath, maxDepth: number): boolean {
  return groupPath.length < maxDepth;
}

export function canMoveInto<T>(
  tree: ConditionGroup<T>,
  from: ConditionPath,
  toGroupPath: ConditionPath,
  maxDepth: number
): boolean {
  if (from.length === 0) return false;

  const node = getNode(tree, from);
  if (node === undefined) return false;

  const target = getNode(tree, toGroupPath);
  if (target === undefined || !isGroup(target)) return false;

  if (isAtOrBelow(toGroupPath, from)) return false;

  return toGroupPath.length + groupLevels(node) <= maxDepth;
}

// ---------------------------------------------------------------------------
// Editing a tree. Every one returns a new tree and leaves the old one alone.
// ---------------------------------------------------------------------------

export function addCondition<T>(
  tree: ConditionGroup<T>,
  groupPath: ConditionPath,
  leaf: T
): ConditionGroup<T> {
  return editGroup(tree, groupPath, (group) => {
    group.conditions.push(leaf);
  });
}

export function addGroup<T>(
  tree: ConditionGroup<T>,
  groupPath: ConditionPath,
  leaf: T
): ConditionGroup<T> {
  return editGroup(tree, groupPath, (group) => {
    group.conditions.push({ conjunction: "and", conditions: [leaf] });
  });
}

export function updateLeaf<T>(
  tree: ConditionGroup<T>,
  path: ConditionPath,
  leaf: T
): ConditionGroup<T> {
  return editParent(tree, path, (parent, index) => {
    parent.conditions[index] = leaf;
  });
}

export function setGroupConjunction<T>(
  tree: ConditionGroup<T>,
  groupPath: ConditionPath,
  value: Conjunction
): ConditionGroup<T> {
  return editGroup(tree, groupPath, (group) => {
    group.conjunction = value;
  });
}

export function turnIntoGroup<T>(
  tree: ConditionGroup<T>,
  path: ConditionPath
): ConditionGroup<T> {
  return editParent(tree, path, (parent, index) => {
    const node = parent.conditions[index];
    if (node === undefined || isGroup(node)) return;
    parent.conditions[index] = { conjunction: "and", conditions: [node] };
  });
}

export function ungroup<T>(
  tree: ConditionGroup<T>,
  path: ConditionPath
): ConditionGroup<T> {
  if (path.length === 0) return clone(tree);

  return editParent(tree, path, (parent, index) => {
    const group = parent.conditions[index];
    if (group === undefined || !isGroup(group)) return;
    parent.conditions.splice(index, 1, ...group.conditions);
  });
}

export function removeNode<T>(
  tree: ConditionGroup<T>,
  path: ConditionPath
): ConditionGroup<T> {
  if (path.length === 0) return emptyTree<T>();

  const next = clone(tree);
  const parent = parentOf(next, path);
  if (!parent) return next;

  parent.conditions.splice(path[path.length - 1], 1);
  pruneEmpty(next, parent);
  return next;
}

/**
 * Move the node at `from` to `toIndex` of the group at `toGroupPath`, its own
 * group included. A reorder and a reparent are the same edit. `toIndex` is
 * clamped, since a drop past the end means append.
 */
export function moveNode<T>(
  tree: ConditionGroup<T>,
  from: ConditionPath,
  toGroupPath: ConditionPath,
  toIndex: number,
  maxDepth: number
): ConditionGroup<T> {
  const next = clone(tree);

  // The root has no group to leave, and the reorder below skips `canMoveInto`.
  if (from.length === 0 || getNode(next, from) === undefined) return next;

  // A reorder changes no depth, so a tree already past `maxDepth` stays
  // rearrangeable.
  const reorder = samePath(from.slice(0, -1), toGroupPath);
  if (!reorder && !canMoveInto(next, from, toGroupPath, maxDepth)) return next;

  const source = parentOf(next, from);
  const target = getNode(next, toGroupPath);
  if (!source || target === undefined || !isGroup(target)) return next;

  const [node] = source.conditions.splice(from[from.length - 1], 1);
  if (node === undefined) return next;

  target.conditions.splice(
    Math.max(0, Math.min(toIndex, target.conditions.length)),
    0,
    node
  );

  if (source !== target) pruneEmpty(next, source);
  return next;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clone<T>(tree: ConditionGroup<T>): ConditionGroup<T> {
  try {
    return structuredClone(tree);
  } catch {
    return JSON.parse(JSON.stringify(tree));
  }
}

function parentOf<T>(
  tree: ConditionGroup<T>,
  path: ConditionPath
): ConditionGroup<T> | undefined {
  const node = getNode(tree, path.slice(0, -1));
  return node !== undefined && isGroup(node) ? node : undefined;
}

/** Clone, resolve, bail if the path names nothing, then apply `edit`. */
function editGroup<T>(
  tree: ConditionGroup<T>,
  groupPath: ConditionPath,
  edit: (group: ConditionGroup<T>) => void
): ConditionGroup<T> {
  const next = clone(tree);
  const group = getNode(next, groupPath);
  if (group !== undefined && isGroup(group)) edit(group);
  return next;
}

/** `editGroup`, addressed by the node instead of the group holding it. */
function editParent<T>(
  tree: ConditionGroup<T>,
  path: ConditionPath,
  edit: (parent: ConditionGroup<T>, index: number) => void
): ConditionGroup<T> {
  return editGroup(tree, path.slice(0, -1), (parent) =>
    edit(parent, path[path.length - 1])
  );
}

/** Whether `path` addresses `other` or something inside it. */
function isAtOrBelow(path: ConditionPath, other: ConditionPath): boolean {
  return path.length >= other.length && other.every((i, d) => i === path[d]);
}

/** How many levels of group a node is: 0 for a leaf, 1 for a group of leaves. */
function groupLevels<T>(node: ConditionNode<T>): number {
  if (!isGroup(node)) return 0;
  return (
    1 +
    node.conditions.reduce(
      (deepest, child) => Math.max(deepest, groupLevels(child)),
      0
    )
  );
}

function parentGroupOf<T>(
  root: ConditionGroup<T>,
  child: ConditionNode<T>
): ConditionGroup<T> | null {
  if (root.conditions.includes(child)) return root;
  for (const node of root.conditions) {
    if (!isGroup(node)) continue;
    const found = parentGroupOf(node, child);
    if (found) return found;
  }
  return null;
}

/**
 * An emptied group goes, cascading up. By reference, not path: a splice
 * invalidates every path after it. `parentGroupOf` answers null for the root,
 * so the root is never pruned.
 */
function pruneEmpty<T>(
  root: ConditionGroup<T>,
  group: ConditionGroup<T>
): void {
  if (group.conditions.length > 0) return;

  const parent = parentGroupOf(root, group);
  if (!parent) return;

  parent.conditions.splice(parent.conditions.indexOf(group), 1);
  pruneEmpty(root, parent);
}
