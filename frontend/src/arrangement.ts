// The client half of arranging: the whole ordered list goes up and the server reduces it.
// Nothing here is a store; a save returns the prefix's navigation and the caller swaps it in.

import { call } from "frappe-ui";
import type { Navigation, NavigationItem } from "@/boot";

/** Which of the two containers is being arranged. */
export type Container = "Rail" | "Sidebar";

/**
 * Whose layer. `user` is always the session user; `site` is what everyone sees and needs a
 * System Manager.
 */
export type Scope = "user" | "site";

/**
 * A row as the editor holds it. `hidden` is absent from `boot.navigation`, so the editor
 * asks for it back.
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
 * Move one row one place among its siblings, not its neighbours in the flat list. At the
 * end of its group it stays put.
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
 * Move one row to where another sits. Refused, list unchanged, unless they share a parent:
 * a drop must never reparent.
 */
export function dropOn(items: ArrangedItem[], key: string, onto: string): ArrangedItem[] {
	const item = items.find((entry) => entry.key === key);
	const target = items.find((entry) => entry.key === onto);

	if (!item || !target || item === target) return items;
	if (parentOf(item) !== parentOf(target)) return items;

	const order = siblings(items);
	const group = [...(order.get(parentOf(item)) ?? [])];
	// Downwards lands after the target, upwards before it: the row takes the target's place.
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
 * with it. A row whose parent is missing is appended, never dropped.
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
