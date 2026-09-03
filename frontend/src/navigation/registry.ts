// Type name -> renderer, and the two failure paths: no renderer, and a renderer that throws.
// Both skip the item and log once; one app's bad row must not blank the rail.

import type { NavigationItem } from "@/boot";
import { itemRenderers } from "@/contributions/registry";
import type { ItemContext, ItemRenderer, Rendering } from "./types";

/** One line per type per page session, not one per render. */
const reported = new Set<string>();

/**
  * A `Sidebar` item resolves rows inside its sidebar, so two sidebars pointing at each other
  * would recurse. A depth, not a key set: a key is unique only within one container.
 */
const MAX_DEPTH = 8;
let depth = 0;

export function rendererFor(itemType: string): ItemRenderer | undefined {
	return itemRenderers[itemType];
}

/** What this item does, or `null` if it cannot be drawn here. */
export function renderingOf(
	item: NavigationItem,
	context: ItemContext
): Rendering | null {
	const renderer = rendererFor(item.item_type);

	if (!renderer) {
		report(
			item.item_type,
			`[frappe] no renderer for navigation item type '${item.item_type}'; ` +
				`item '${item.key}' is not drawn. A kind is two files: the type record and ` +
				`<module>/navigation_item_type/<scrubbed>/frontend/item.js.`
		);
		return null;
	}

	if (depth >= MAX_DEPTH) return null;
	depth += 1;

	try {
		const rendering = renderer.render(item, context);

		// Resolved here so an unresolvable route fails in this handler, not inside `RouterLink`.
		if (rendering && "to" in rendering) context.router.resolve(rendering.to);

		return rendering;
	} catch (error) {
		report(
			item.item_type,
			`[frappe] the renderer for '${item.item_type}' threw on item '${item.key}'; ` +
				`it is not drawn.`,
			error
		);
		return null;
	} finally {
		depth -= 1;
	}
}

/**
  * An authored label wins and is never translated; then the renderer's fallback; then the destination.
 */
export function labelOf(item: NavigationItem, context: ItemContext): string {
	if (item.label) return item.label;

	const renderer = rendererFor(item.item_type);

	try {
		const fallback = renderer?.label?.(item, context);
		if (fallback) return fallback;
	} catch {
		// A renderer that cannot name the item still gets its destination drawn.
	}

	return item.link_to ?? item.key;
}

function report(itemType: string, message: string, error?: unknown) {
	if (reported.has(itemType)) return;
	reported.add(itemType);
	// Console only: the client has no working Error Log channel on this branch.
	if (error) console.error(message, error);
	else console.error(message);
}

/** Cleared between page sessions, so a reload reports afresh. */
export function resetNavigationReports() {
	reported.clear();
}
