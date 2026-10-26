// Where an app's or a module's bare address lands: the first row its navigation resolves to
// as a route in this prefix. Computed from `boot.navigation`, so it costs no request.

import type { RouteLocationRaw, Router } from "vue-router";
import type { Boot, NavigationItem } from "@/boot";
import type { Addresses } from "@/addresses";
import { itemContext } from "./context";
import type { ItemContext } from "./types";

/** The landing of `home`, or of `module` when a slug is given; null when nothing opens. */
export function landingOf(
	boot: Boot,
	addresses: Addresses,
	router: Router,
	moduleSlug?: string
): RouteLocationRaw | null {
	const navigation = boot.navigation;
	if (!navigation) return null;

	const context = itemContext(boot, addresses, router, navigation.rail, navigation.sidebars);
	if (!moduleSlug) return firstRoute(navigation.rail, context, ["home"]);

	// A module never lands on another landing, so no redirect can loop.
	const address = moduleSidebar(moduleSlug);
	const landing = firstRoute(navigation.sidebars[address] ?? [], context, ["home", "module"]);
	if (!landing || typeof landing === "string") return landing;

	// The first row usually sits in several sidebars, so the module's own is named for the panel.
	return { ...landing, query: { ...landing.query, sidebar: address } };
}

/** The first item that resolves to a route, other than a route named in `landings`. */
function firstRoute(
	items: NavigationItem[],
	context: ItemContext,
	landings: string[]
): RouteLocationRaw | null {
	for (const item of items) {
		const rendering = context.renderingOf(item);
		if (!rendering || !("to" in rendering)) continue;

		const name = context.router.resolve(rendering.to).name;
		if (typeof name === "string" && landings.includes(name)) continue;
		return rendering.to;
	}

	return null;
}

// Boot files a module's sidebar under the scrub of `Module Def <name>`, and the address table
// spells the module's slug as that scrub hyphenated.
function moduleSidebar(moduleSlug: string): string {
	return `module_def_${moduleSlug.replaceAll("-", "_")}`;
}
