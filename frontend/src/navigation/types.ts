// The contract a navigation item kind's `item.js` implements. The framework's own kinds go
// through it unmodified; the registry holds no built-in table.

import type { RouteLocationRaw, Router } from "vue-router";
import type { Boot, NavigationItem } from "@/boot";
import type { Addresses } from "@/addresses";
import type { ContentEntry } from "@/contents";

/**
  * What one item resolves to: a route in this prefix, an absolute href (a full document
  * load, so an `<a>`), a heading, or rows fetched on demand. `sidebar` annotates a destination.
 */
export type Rendering =
	| { to: RouteLocationRaw; sidebar?: string }
	| { href: string; sidebar?: string }
	| { group: true }
	| { expand: () => Promise<NavigationItem[]> };

/**
  * Everything a renderer may know, as a parameter: a contributed renderer imports only `@shell`.
 */
export type ItemContext = {
	boot: Boot;
	addresses: Addresses;
	/**
	 * For the registry to resolve what a renderer returns before `RouterLink` throws mid-render.
	 */
	router: Router;
	/** Every sidebar in this prefix, keyed by scrubbed address. */
	sidebars: Record<string, NavigationItem[]>;
	/**
	 * The whole list this item belongs to; `Module Contents` measures what is left against it.
	 */
	items: NavigationItem[];
	/** The contributed pages this prefix serves. */
	pages: { slug: string; title?: string }[];
	/** What a module contains, permission-filtered (`contents.ts`). */
	contentsOf(moduleSlug: string): Promise<ContentEntry[]>;
	/**
	 * Another item's rendering; a `Sidebar` item resolves its sidebar's first row through it.
	 * Recursion is depth-guarded by the registry, not by the renderer.
	 */
	renderingOf(item: NavigationItem): Rendering | null;
};

/**
  * A renderer, as an app's `item.js` default-exports it. `render` returns `null` when the
  * item cannot be drawn here and the row is skipped; `label` is only the unlabelled fallback.
 */
export type ItemRenderer = {
	render(item: NavigationItem, context: ItemContext): Rendering | null;
	label?(item: NavigationItem, context: ItemContext): string | undefined;
};
