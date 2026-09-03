// Which row the address is on, and therefore which sidebar is open.
//
// Charter point 7: navigation follows the address, never the reverse. This module is the
// function from the address to the shell around it.
//
// That function takes one extra input, and #42432 narrowed the charter point to allow it:
// where SEVERAL panels cover the address equally, the one the reader is already in wins.
// One in five ERPNext destinations sits in more than one panel and `Item` sits in six, so
// without it a reader is yanked out of the panel they are working in as the ordinary case.
// The narrowing is bounded: the preference only ever picks among panels the address itself
// already allows, never invents one and never beats a deeper cover — so a COLD load is
// still a pure function of the path, and one URL still gives two colleagues one shell.
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
 * Deepest coverage always wins. Among covers of EQUAL depth, `prefer` decides: the earliest
 * of its sidebars to appear wins, and where it names none of them the first in list order
 * does, which is the rail read top to bottom.
 *
 * `prefer` is the reader's continuity, most wanted first — the panel open right now, then
 * whatever this tab last resolved for this address (#42464). It is a tie-break and only a
 * tie-break: a panel in it that does not cover the address, or covers it less deeply than
 * another, loses anyway. That is what keeps a cold load a function of the path.
 *
 * Where ONE panel lists a destination twice, the first row going down the panel wins the
 * highlight — the `>` below, since both rows are the same depth in the same panel. Recorded
 * as a decision rather than left as an accident (#42432): the reader is never relocated, so
 * the cost is a highlight one row from where they clicked, and the likely real case is a
 * pinned row above a categorised copy of itself, where reading order highlights the pinned
 * one. Lighting both stays out — this module exists because `router-link-active` lit two
 * rows at once, and two rows carrying `aria-current="page"` tell a screen reader there are
 * two current pages.
 *
 * An address no destination covers returns `{}`: no highlight, and no panel. The preference
 * cannot rescue it, because there is nothing for it to choose between.
 */
export function currentFrom(
	destinations: Destination[],
	path: string,
	prefer: string[] = []
): CurrentNavigation {
	// How wanted this panel is: its place in `prefer`, or one past the end for a panel nobody
	// asked for. Lower is better, so an unpreferred cover never displaces a preferred one.
	const rank = (found: CurrentNavigation) => {
		const place = found.sidebar ? prefer.indexOf(found.sidebar) : -1;
		return place === -1 ? prefer.length : place;
	};

	let best: CurrentNavigation = {};
	let depth = -1;
	let wanted = prefer.length;

	for (const destination of destinations) {
		const covers = coverage(path, destination.path);
		// A row that does not cover the address is not a candidate at all, however wanted its
		// panel is. Checked before the depth compare, since -1 ties the "nothing yet" depth.
		if (covers < 0 || covers < depth) continue;

		const place = rank(destination.found);
		// Strictly deeper always wins. At equal depth only a STRICTLY more wanted panel does,
		// so first-in-list still breaks a tie nothing prefers.
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
