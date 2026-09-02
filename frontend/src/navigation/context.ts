// The world one renderer is handed.
//
// Composed once per list rather than once per item: `items` and `sidebars` are the same
// for every row, and `renderingOf` has to close over the finished context so that a
// `Sidebar` item can resolve rows it did not author.

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
		// This prefix's pages only, which is the same filter the route table applies: a
		// `Page` item can only point at a page this document can actually route to.
		pages: pages.filter((page) => page.app === boot.app),
		// Rejects rather than answering empty off the index, which belongs to no app. `[]`
		// is a REAL answer here — a module whose contents this person may not read — so
		// returning it for a question that was never asked would put "nothing left in this
		// module" on screen over a request that never happened (`contents.ts`).
		contentsOf: (moduleSlug) =>
			boot.app
				? fetchContents(boot.app, moduleSlug)
				: Promise.reject(new Error("no app serves this prefix")),
		renderingOf: (item) => renderingOf(item, context),
	};

	return context;
}
