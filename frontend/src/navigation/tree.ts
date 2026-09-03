// The flat list, as a tree.
//
// `parent_key` is the whole of hierarchy (#42227), and the server sends one flat,
// ordered list — so the shape has to be rebuilt here. Two orders live in that list, the
// list's and the tree's, and #42403 found every one of its defects in code that edited
// one and forgot the other. This module reads rather than edits, and it keeps both: a
// child follows its parent in the flat order, so walking the tree depth-first yields the
// list back.

import type { NavigationItem } from "@/boot";

export type ItemNode = {
	item: NavigationItem;
	children: ItemNode[];
};

/**
 * Build the tree the rail draws.
 *
 * The server has already promoted an item whose parent is GONE to the top level
 * (`_promote_orphans`), so nothing here has to. What it cannot have fixed is a `parent_key`
 * chain that closes on itself: every row in a cycle has a parent that is present, so the
 * server's check passes and the rows attach to each other and to no root. Rendering the
 * tree would then simply omit them, which is a silent drop of authored navigation — so a
 * cycle is broken here, at the row that closes it, and that row is lifted to the top level.
 *
 * Every row in the cycle is lifted, not just one. Breaking only the first would leave the
 * rest hanging off a row that is now a root, which reads as a deliberate nesting nobody
 * authored; a flat row is visibly the odd one out, which is what a reader needs.
 *
 * `onCycle` reports it. The caller logs; this stays a pure function, because the tree is
 * rebuilt on every render of a reactive list and a logger inside it would fire per frame.
 */
export function buildTree(
	items: NavigationItem[],
	onCycle?: (key: string) => void
): ItemNode[] {
	const nodes = new Map<string, ItemNode>();
	// Last one wins, matching the server's own merge: a duplicate key is one item that was
	// written twice, not two items. Building the index first is also what lets a child
	// appear BEFORE its parent in the flat list without being orphaned.
	for (const item of items) nodes.set(item.key, { item, children: [] });

	const roots: ItemNode[] = [];

	// Over the INDEX, not over `items`. A key that appears twice is one node in the map, so
	// walking the list would place that one node twice — the same object under two parents,
	// or twice at the top level, which Vue then renders as duplicate rows under a duplicate
	// `:key`. A `Map` keeps first-seen order while `set` overwrites the value, so this is
	// the list's order with the later row's content, which is what "written twice" means.
	for (const node of nodes.values()) {
		const item = node.item;
		const parent = item.parent_key ? nodes.get(item.parent_key) : undefined;

		if (!parent || parent === node || descends(nodes, item.parent_key!, item.key)) {
			if (parent) onCycle?.(item.key);
			roots.push(node);
			continue;
		}

		parent.children.push(node);
	}

	return roots;
}

/** Does `from` already sit under `key`? Walking up from `from` answers it in one pass. */
function descends(
	nodes: Map<string, ItemNode>,
	from: string,
	key: string
): boolean {
	const seen = new Set<string>();
	let at: string | undefined = from;

	while (at && !seen.has(at)) {
		if (at === key) return true;
		seen.add(at);
		at = nodes.get(at)?.item.parent_key;
	}

	return false;
}

/** Is `key` this node or anywhere beneath it? */
export function containsKey(node: ItemNode, key: string): boolean {
	return node.item.key === key || node.children.some((child) => containsKey(child, key));
}
