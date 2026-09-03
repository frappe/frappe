// Which row the address is on, and therefore which sidebar is open.
//
// Charter point 7: navigation follows the address, never the reverse. Among panels covering
// it EQUALLY the reader's open one wins, but a cold load is still the path alone.
//
// It is not `router-link-active`. Two reasons, and both are real rather than tidiness. A
// rail item of type `Sidebar` resolves to the first destination INSIDE its sidebar
// (`sidebar/frontend/item.js`), so standing on the third row of that sidebar leaves the
// rail item's own link inactive while the panel it opens is exactly where you are; and
// `router-link-active` is prefix-based per link, so a list and one of its saved views both
// match `/sales-invoice/view/open` and two rows light up. One winner, chosen here, is the
// only version of "the rail and the panel highlight whatever the current URL resolves to"
// that a reader can act on.

import type { NavigationItem } from "@/boot";
import type { ItemContext, Rendering } from "./types";

/** One route navigation can be standing on, and what being on it means. */
export type Destination = { path: string; found: CurrentNavigation };

/**
 * One item context per container, because a context is composed once per LIST and there are
 * two kinds of list here. `Module Contents` is what makes the difference real: it measures
 * "what is left of this module" against `context.items`, so a row in a sidebar handed the
 * rail's context would hide the doctypes the RAIL already shows and repeat the ones its own
 * panel does.
 */
export type NavigationContexts = {
	rail: ItemContext;
	sidebars: Record<string, ItemContext>;
};

export type CurrentNavigation = {
	/** The rail row to highlight: the destination itself, or the item that opens the panel. */
	railKey?: string;
	/** The scrubbed address of the sidebar to show, if the address is inside one (#42356). */
	sidebar?: string;
	/** The row inside that sidebar to highlight. */
	rowKey?: string;
};

/**
 * How specifically `itemPath` covers `currentPath` — its segment count, or -1 for no cover.
 *
 * Segment-wise rather than `startsWith`, which would read `/sales-orders` as sitting under
 * `/sales-order`. A list covers its own records and its saved views, so `/sales-invoice`
 * stays lit while you read `/sales-invoice/SI-001`; and where a list and a view both cover
 * the address, the view is deeper and wins.
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
 * Every route in this prefix that navigation can be standing on, and what each one means.
 *
 * Separate from the match because the two change at different rates. Resolving a
 * destination costs a `renderingOf` and a `router.resolve`, twice over — the registry
 * resolves once to keep an unresolvable route out of `RouterLink` — and the framework's own
 * prefix carries 194 rail items (#42362). Doing that per navigation would put hundreds of
 * route resolutions in the way of every click. The payload changes only on a save, so this
 * is computed against the payload and the match against the path.
 *
 * Everything with a route competes: the rail's own rows, and the rows of every sidebar the
 * rail can open. A rail item that opens a sidebar competes THROUGH that sidebar's rows
 * rather than through its own destination, because its own destination is one of those rows
 * already (`sidebar/frontend/item.js`) and counting it twice would let the linked item beat
 * the panel it opens — the panel would then open with nothing marked inside it.
 *
 * Order is the order the person is looking at: the rail top to bottom, and a linked item's
 * panel where the item sits. That is what breaks a tie, and ties are ordinary rather than
 * exotic — #42357 counted 101 rows in ERPNext linking outside their own module, so one
 * address really does sit in two places.
 */
export function navigationDestinations(
	rail: NavigationItem[],
	sidebars: Record<string, NavigationItem[]>,
	contexts: NavigationContexts
): Destination[] {
	const destinations: Destination[] = [];
	const router = contexts.rail.router;

	const add = (rendering: Rendering | null, found: CurrentNavigation) => {
		// `href` rows leave the prefix and `group`/`expand` rows go nowhere, so neither can be
		// where you are standing.
		if (!rendering || !("to" in rendering)) return;

		// Resolvable, because `renderingOf` already resolved it once (`registry.ts`).
		destinations.push({ path: router.resolve(rendering.to).path, found });
	};

	for (const item of rail) {
		const rendering = contexts.rail.renderingOf(item);
		const sidebar = rendering && "sidebar" in rendering ? rendering.sidebar : undefined;

		if (sidebar) {
			// Its own rows, through their own context — the one the panel will draw them with,
			// so what is a destination here is a destination there.
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
 * The rail row, the sidebar and the row inside it that `path` is standing on.
 *
 * `prefer` holds the reader's panels, most wanted first, and breaks ties only: deeper
 * coverage still wins, and an address nothing covers returns `{}`.
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

		// Strictly more wanted, so list order still breaks a tie nothing prefers: the rail top
		// to bottom, and the first of two rows one panel points at the same place.
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
