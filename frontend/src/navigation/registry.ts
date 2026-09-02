// Type name -> renderer, and what happens when there is no renderer to find.
//
// There is no built-in table here. The framework's eight kinds arrive through
// `contributions/registry.ts` exactly as an app's would, so this file cannot tell one
// from the other and has no case to grow when a ninth lands (DP2).
//
// It also owns the two failure paths, because both must be answered once rather than in
// eight renderers:
//
//   - **No renderer.** #42228 chose skip-and-log over failing the render, which is
//     #42070's degrade rather than #42069's fail-hard. The item is silently absent from
//     the rail today; this is what makes it loud.
//   - **A renderer that throws.** `routeFor` throws for a doctype the address table has
//     never heard of, which is a real state for an item pointing at an app that has since
//     been uninstalled. A renderer is app code, so it is treated exactly as a missing one:
//     skip the item, log once. One app's bad row must not blank the rail.

import type { NavigationItem } from "@/boot";
import { itemRenderers } from "@/contributions/registry";
import type { ItemContext, ItemRenderer, Rendering } from "./types";

/** One line per type per page session, not one per render. */
const reported = new Set<string>();

/**
 * A `Sidebar` item's destination is the first destination INSIDE its sidebar, so resolving
 * one item can resolve others, and two sidebars pointing at each other would otherwise be
 * a stack overflow that takes the shell down with it.
 *
 * A DEPTH count rather than a set of keys, and the difference is a real bug rather than
 * taste: a key identifies a row within one container, so the rail and a sidebar may each
 * hold a row called `accounts` without either being a cycle. Guarding on the key would
 * read the second as a repeat of the first and quietly render the rail item as
 * independent — a link silently missing, with nothing said. Depth cannot confuse two rows
 * for one, and the ceiling is far above any real nesting.
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

		// A route that does not resolve throws inside `RouterLink`, during render, where
		// nothing catches it — so one contributed renderer returning a name the route table
		// does not hold would blank the whole rail. Resolving it HERE puts that failure back
		// inside the handler this file already promises, which is skip-and-log (#42228).
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
 * What a reader sees on this item.
 *
 * An authored label always wins and is rendered literally — never translated, because
 * whoever typed it typed it in the language they meant (#42230). Only the fallback is the
 * renderer's, and only when it has one: the last resort is the item's own destination,
 * which is what a derived rail row is — an address and no authored presentation.
 */
export function labelOf(item: NavigationItem, context: ItemContext): string {
	if (item.label) return item.label;

	const renderer = rendererFor(item.item_type);

	try {
		const fallback = renderer?.label?.(item, context);
		if (fallback) return fallback;
	} catch {
		// A renderer that cannot even name the item still gets its destination drawn, if
		// `render` managed one. Falling through is the whole handler.
	}

	return item.link_to ?? item.key;
}

function report(itemType: string, message: string, error?: unknown) {
	if (reported.has(itemType)) return;
	reported.add(itemType);
	// Console only. #42228 asked for `frappe.log_error` as well, and the client's one
	// channel to the Error Log — `reportCustomizationError`, which posts to
	// `frappe.desk.customization_error.report_customization_error` — has no Python side on
	// this branch at all; the endpoint exists in no app on the bench. Calling it would be a
	// line that reads as reporting and does nothing, so this says what it does.
	if (error) console.error(message, error);
	else console.error(message);
}

/** Cleared between page sessions, so a reload reports afresh. */
export function resetNavigationReports() {
	reported.clear();
}
