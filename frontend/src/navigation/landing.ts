// Where an app's or a module's bare address lands: the first row its navigation resolves to
// as a route in this prefix. Computed from `boot.navigation`, so it costs no request.

import type { RouteLocation, Router } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import { itemContext } from "./context";
import type { ItemContext, Rendering } from "./types";

/** The landing of `home`, or of `module` when a slug is given; null when nothing opens. */
export function landingOf(
	boot: Boot,
	addresses: Addresses,
	router: Router,
	moduleSlug?: string
): RouteLocation | null {
	const navigation = boot.navigation;
	if (!navigation) return null;

	const context = itemContext(boot, addresses, router, navigation.rail, navigation.sidebars);
	return moduleSlug ? moduleLanding(moduleSlug, context) : homeLanding(context);
}

/** The first rail item that opens a route; a module item counts only if its module lands. */
function homeLanding(context: ItemContext): RouteLocation | null {
	for (const item of context.items) {
		const route = routeOf(context.renderingOf(item), context);
		if (!route || route.name === "home") continue;
		if (route.name !== "module") return route;

		const landing = moduleLanding(String(route.params.module), context);
		if (landing) return landing;
	}

	return null;
}

/** The first row of the module's sidebar that opens a route other than a landing. */
function moduleLanding(moduleSlug: string, context: ItemContext): RouteLocation | null {
	const address = moduleSidebar(moduleSlug);

	for (const row of context.sidebars[address] ?? []) {
		const route = routeOf(context.renderingOf(row), context);
		if (!route || route.name === "home" || route.name === "module") continue;

		// The first row usually sits in several sidebars, so the module's own is named for the panel.
		return context.router.resolve({ path: route.path, query: { ...route.query, sidebar: address } });
	}

	return null;
}

function routeOf(rendering: Rendering | null, context: ItemContext): RouteLocation | null {
	return rendering && "to" in rendering ? context.router.resolve(rendering.to) : null;
}

// Boot files a module's sidebar under the scrub of `Module Def <name>`, and the address table
// spells the module's slug as that scrub hyphenated; `test_shell.py` pins the two together.
function moduleSidebar(moduleSlug: string): string {
	return `module_def_${moduleSlug.replaceAll("-", "_")}`;
}
