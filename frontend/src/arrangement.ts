// ARRANGING — the client half of desk v2's first user-state write.
//
// The whole ordered list goes up; the reduction to what actually changed happens on the server
// (#42363). That division is not an accident of where the code was easier to write. A client
// that sent anchors would be computing identity and difference against a copy of the base it
// may already be holding stale, which is the mistake desk v1 makes in the other direction: its
// sidebar manager recomputes the server's item key in JS and gets it wrong two ways, leaving
// `filters` out of a key the server includes and returning a raw `"type|label"` where the server
// returns a hash. Desk v2's key is authored, arrives on the wire, and is never computed here.
//
// Nothing in this file is a store. A save returns the whole `{rail, sidebars}` for the prefix and
// the caller swaps it into `boot.navigation` wholesale, so the arrangement a person is looking at
// and the navigation the shell renders never drift into two copies that have to be reconciled.

import { call } from "frappe-ui";
import type { Navigation, NavigationItem } from "@/boot";

/** Which of the two containers is being arranged. They are two presentations of one model. */
export type Container = "Rail" | "Sidebar";

/**
 * Whose layer. `user` is always the session user — the endpoints take no user argument, so
 * arranging somebody else's navigation is not a request this client could make even by mistake.
 * `site` is what everyone sees and needs a System Manager.
 */
export type Scope = "user" | "site";

/**
 * A row as the editor holds it: what the payload carries, plus the hidden flag.
 *
 * `hidden` is absent from `boot.navigation` — boot drops hidden rows, because the browser cannot
 * render a row it must not show. The editor asks for them back, since a hide nobody can see is a
 * hide nobody can undo.
 */
export type ArrangedItem = NavigationItem & { hidden?: 1 };

/** The address of one container: an app name for a rail, a scrubbed address for a sidebar. */
export type Address = { container: Container; address: string };

export async function fetchArrangement(
	{ container, address }: Address,
	scope: Scope = "user"
): Promise<ArrangedItem[]> {
	return await call("frappe.shell.arrangement.get_arrangement", {
		container,
		address,
		scope,
	});
}

export async function saveArrangement(
	{ container, address }: Address,
	items: ArrangedItem[],
	scope: Scope = "user"
): Promise<Navigation> {
	return await call("frappe.shell.arrangement.save_arrangement", {
		container,
		address,
		scope,
		items,
	});
}

export async function resetArrangement(
	{ container, address }: Address,
	scope: Scope = "user"
): Promise<Navigation> {
	return await call("frappe.shell.arrangement.reset_arrangement", {
		container,
		address,
		scope,
	});
}

/**
 * Move one row one place among its own siblings, and give back a new list.
 *
 * Siblings, not neighbours in the flat list. The payload is flat and the rail draws it as a
 * tree, so the row above a section's first child is the section itself — stepping onto it would
 * read as "move out of this section", which is a different edit and not the one the arrow means.
 *
 * A row already at the end of its group does not move, and does not wrap. The list is short
 * enough to see all of, so wrapping would look like a bug rather than a feature.
 */
export function move(items: ArrangedItem[], key: string, by: 1 | -1): ArrangedItem[] {
	const item = items.find((entry) => entry.key === key);
	if (!item) return items;

	const order = siblings(items);
	const group = order.get(parentOf(item)) ?? [];
	const at = group.indexOf(key);
	if (at + by < 0 || at + by >= group.length) return items;

	const swapped = [...group];
	[swapped[at], swapped[at + by]] = [swapped[at + by], swapped[at]];
	order.set(parentOf(item), swapped);

	return flatten(items, order);
}

/**
 * Move one row to where another sits, which is what a drag means.
 *
 * Only between siblings. Dropping onto a row under a different parent would mean two edits at
 * once — a reparent and a reorder — and a drag that silently did the first is how somebody's
 * whole section ends up somewhere they did not put it. A drop that is not a sibling's is
 * refused by returning the list unchanged, which reads as the row springing back.
 */
export function dropOn(items: ArrangedItem[], key: string, onto: string): ArrangedItem[] {
	const item = items.find((entry) => entry.key === key);
	const target = items.find((entry) => entry.key === onto);

	if (!item || !target || item === target) return items;
	if (parentOf(item) !== parentOf(target)) return items;

	const order = siblings(items);
	const group = [...(order.get(parentOf(item)) ?? [])];
	// Dragged downwards a row lands after the row it was dropped on, upwards before it — which
	// is the same rule either way: it takes the place the target is standing in.
	const downwards = group.indexOf(key) < group.indexOf(onto);

	group.splice(group.indexOf(key), 1);
	group.splice(group.indexOf(onto) + (downwards ? 1 : 0), 0, key);
	order.set(parentOf(item), group);

	return flatten(items, order);
}

function parentOf(item: ArrangedItem): string | null {
	return item.parent_key ?? null;
}

/** The keys under each parent, in their current order. `null` is the top level. */
function siblings(items: ArrangedItem[]): Map<string | null, string[]> {
	const order = new Map<string | null, string[]>();

	for (const item of items) {
		const group = order.get(parentOf(item)) ?? [];
		group.push(item.key);
		order.set(parentOf(item), group);
	}

	return order;
}

/**
 * Rebuild the flat list from the sibling order, depth first, so a section's children travel
 * with it.
 *
 * The list is flat and the tree is `parent_key`, so moving a section by swapping two rows leaves
 * its children where they were — the saved arrangement is still right, because the reduction
 * compares each parent's children separately, but the editor would draw rows under a heading
 * they do not belong to. Re-flattening makes what is on screen and what is in the list the same
 * thing, which is the only version anybody can check by looking.
 *
 * A row whose parent is not in the list is appended rather than dropped. The server promotes
 * orphans before sending, so this should not arise; losing a row to a rule about drawing it
 * would be much worse than showing it at the end.
 */
function flatten(items: ArrangedItem[], order: Map<string | null, string[]>): ArrangedItem[] {
	const byKey = new Map(items.map((item) => [item.key, item]));
	const flat: ArrangedItem[] = [];
	const seen = new Set<string>();

	const walk = (parent: string | null) => {
		for (const key of order.get(parent) ?? []) {
			const item = byKey.get(key);
			if (!item || seen.has(key)) continue;
			seen.add(key);
			flat.push(item);
			walk(key);
		}
	};

	walk(null);

	return [...flat, ...items.filter((item) => !seen.has(item.key))];
}
