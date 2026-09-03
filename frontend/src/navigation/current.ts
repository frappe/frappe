// Which row the address is on, and so which sidebar is open. Not `router-link-active`: a
// `Sidebar` rail item's link resolves to a row inside its panel, and prefix matching lights two rows.

import type { NavigationItem } from "@/boot";
import type { ItemContext, Rendering } from "./types";

/** One route navigation can be standing on, and what being on it means. */
export type Destination = { path: string; found: CurrentNavigation };

/**
 * One context per container: `Module Contents` measures against `context.items`, and a
 * sidebar row handed the rail's list would hide the wrong doctypes.
 */
export type NavigationContexts = {
	rail: ItemContext;
	sidebars: Record<string, ItemContext>;
};

export type CurrentNavigation = {
	/** The rail row to highlight: the destination itself, or the item that opens the panel. */
	railKey?: string;
	/** The scrubbed address of the sidebar to show, if the address is inside one. */
	sidebar?: string;
	/** The row inside that sidebar to highlight. */
	rowKey?: string;
};

/**
 * How specifically `itemPath` covers `currentPath`: its segment count, or -1 for no cover.
 * Segment-wise, or `/sales-orders` would sit under `/sales-order`.
 */
export function coverage(currentPath: string, itemPath: string): number {
	const current = currentPath.split("/").filter(Boolean);
	const item = itemPath.split("/").filter(Boolean);

	if (item.length > current.length) return -1;
	for (let index = 0; index < item.length; index += 1) {
		if (item[index] !== current[index]) return -1;
	}

	return item.length;
}

/**
 * Every route navigation can stand on, computed once per payload, not per click. A rail
 * item that opens a sidebar competes through that sidebar's rows, not its own destination.
 */
export function navigationDestinations(
	rail: NavigationItem[],
	sidebars: Record<string, NavigationItem[]>,
	contexts: NavigationContexts
): Destination[] {
	const destinations: Destination[] = [];
	const router = contexts.rail.router;

	const add = (rendering: Rendering | null, found: CurrentNavigation) => {
		// `href` rows leave the prefix and `group`/`expand` rows go nowhere.
		if (!rendering || !("to" in rendering)) return;

		// Resolvable, because `renderingOf` already resolved it once (`registry.ts`).
		destinations.push({ path: router.resolve(rendering.to).path, found });
	};

	for (const item of rail) {
		const rendering = contexts.rail.renderingOf(item);
		const sidebar = rendering && "sidebar" in rendering ? rendering.sidebar : undefined;

		if (sidebar) {
			// Through the sidebar's own context, the one the panel draws them with.
			const inside = contexts.sidebars[sidebar] ?? contexts.rail;
			for (const row of sidebars[sidebar] ?? []) {
				add(inside.renderingOf(row), { railKey: item.key, sidebar, rowKey: row.key });
			}
			continue;
		}

		add(rendering, { railKey: item.key });
	}

	return destinations;
}

/**
 * The rail row, sidebar and row inside it that `path` is standing on. `prefer` breaks ties
 * only: deeper coverage still wins, and an address nothing covers returns `{}`.
 */
export function currentFrom(
	destinations: Destination[],
	path: string,
	prefer: string[] = []
): CurrentNavigation {
	const rank = (found: CurrentNavigation) => {
		const place = found.sidebar ? prefer.indexOf(found.sidebar) : -1;
		return place === -1 ? prefer.length : place;
	};

	let best: CurrentNavigation = {};
	let depth = -1;
	let wanted = prefer.length;

	for (const destination of destinations) {
		const covers = coverage(path, destination.path);
		// -1 ties the starting depth, so a row covering nothing must be dropped before the
		// compare or a preferred panel wins on an address it does not hold.
		if (covers < 0 || covers < depth) continue;

		// Strictly more wanted, so list order still breaks a tie nothing prefers.
		const place = rank(destination.found);
		if (covers > depth || place < wanted) {
			depth = covers;
			wanted = place;
			best = destination.found;
		}
	}

	return best;
}

/** Both halves, for a caller with no reason to hold the destinations. */
export function currentNavigation(
	rail: NavigationItem[],
	sidebars: Record<string, NavigationItem[]>,
	contexts: NavigationContexts,
	path: string,
	prefer: string[] = []
): CurrentNavigation {
	return currentFrom(navigationDestinations(rail, sidebars, contexts), path, prefer);
}
