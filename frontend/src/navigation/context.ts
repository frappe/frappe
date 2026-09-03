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
		// This prefix's pages only, the same filter the route table applies.
		pages: pages.filter((page) => page.app === boot.app),
		// Rejects off the index: `[]` is a real answer here and must not be forged.
		contentsOf: (moduleSlug) =>
			boot.app
				? fetchContents(boot.app, moduleSlug)
				: Promise.reject(new Error("no app serves this prefix")),
		renderingOf: (item) => renderingOf(item, context),
	};

	return context;
}
