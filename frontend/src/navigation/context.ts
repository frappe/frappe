// The world one renderer is handed, composed once per list so `renderingOf` closes over
// the finished context and a `Sidebar` item can resolve rows it did not author.

import type { Router } from "vue-router";
import type { Boot, NavigationItem } from "@/boot";
import type { Addresses } from "@/addresses";
import { fetchContents } from "@/contents";
import { pages } from "@/contributions/registry";
import { renderingOf } from "./registry";
import type { ItemContext } from "./types";

export function itemContext(
	boot: Boot,
	addresses: Addresses,
	router: Router,
	items: NavigationItem[],
	sidebars: Record<string, NavigationItem[]>
): ItemContext {
	const context: ItemContext = {
		boot,
		addresses,
		router,
		items,
		sidebars,
		// The pages the route table kept: this prefix's own, less any whose address is taken.
		pages: pages.filter((page) => router.hasRoute(`page:${page.app}:${page.slug}`)),
		// Rejects off the index: `[]` is a real answer here and must not be forged.
		contentsOf: (moduleSlug) =>
			boot.app
				? fetchContents(boot.app, moduleSlug)
				: Promise.reject(new Error("no app serves this prefix")),
		renderingOf: (item) => renderingOf(item, context),
	};

	return context;
}
