// The flat list as a tree. A child follows its parent in the flat order, so walking the
// tree depth-first yields the list back; this module reads and never edits.

import type { NavigationItem } from "@/boot";

export type ItemNode = {
	item: NavigationItem;
	children: ItemNode[];
};

/**
 * Build the tree. The server promotes orphans, but a `parent_key` cycle passes its check, so
 * every row in one is lifted to the top level here and reported through `onCycle`.
 */
export function buildTree(
	items: NavigationItem[],
	onCycle?: (key: string) => void
): ItemNode[] {
	const nodes = new Map<string, ItemNode>();
	// Last one wins, as in the server's merge. Indexing first lets a child precede its parent.
	for (const item of items) nodes.set(item.key, { item, children: [] });

	const roots: ItemNode[] = [];

	// Over the index, not `items`: a duplicate key is one node, and walking the list would
	// place it twice, which Vue renders as duplicate rows under one `:key`.
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
