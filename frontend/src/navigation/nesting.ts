// How deep a navigation list may go, for the editor's drag and "Move to…". The server holds
// the same rule in `frappe/desk/doctype/navigation_item/nesting.py` and enforces it; this only keeps the editor from
// offering a move the save would refuse. Both read `tests/nesting.cases.json`.

import type { NavigationItem } from "@/boot";

export type NavigationContainer = "Rail" | "Sidebar";

const SECTION = "Section";

/**
 * Whether `item` may sit under `parent` (`null` is the top level) in `items`, the list both
 * live in. The rows under `item` move with it, so a move that pushes one of them past the
 * cap is refused too.
 */
export function canNestUnder(
	item: NavigationItem,
	parent: NavigationItem | null,
	container: NavigationContainer,
	items: NavigationItem[]
): boolean {
	const before = new Set(rowsPastTheCap(items, container));
	const moved = items.map((row) =>
		row.key === item.key ? { ...row, parent_key: parent?.key } : row
	);

	return rowsPastTheCap(moved, container).every((key) => before.has(key));
}

function rowsPastTheCap(items: NavigationItem[], container: NavigationContainer): string[] {
	const rows = new Map(items.map((row) => [row.key, row]));

	return items.filter((row) => isPastTheCap(row, rows, container)).map((row) => row.key);
}

function isPastTheCap(
	row: NavigationItem,
	rows: Map<string, NavigationItem>,
	container: NavigationContainer
): boolean {
	if (!row.parent_key) return false;
	if (container === "Rail" || row.item_type === SECTION) return true;

	const parent = rows.get(row.parent_key);
	if (!parent || parent.item_type === SECTION) return false;

	// Under an item, which may itself sit only at the top level or in a section.
	const grandparent = parent.parent_key ? rows.get(parent.parent_key) : undefined;
	return !!grandparent && grandparent.item_type !== SECTION;
}
