// What a navigation item DOES, and who gets to say so.
//
// #42228 decided a kind is two files — a `Navigation Item Type` record, and the JS that
// says what an item of that kind does on click — and named a path without naming the
// contract. This file is the contract.
//
// The framework's own eight kinds go through it unmodified: `DocType`, `Record`,
// `Module`, `Module Contents`, `Page`, `Section`, `Sidebar` and `Link` each ship a
// renderer at the ordinary contribution path, discovered by the ordinary plugin, and the
// registry holds no built-in table at all. That is DP2 taken literally — if the framework
// needed a back door to draw its own rail, the front door would not be finished — and it
// is what makes "an app contributes a kind" (#42424) a matter of writing two files rather
// than of the framework growing a case.

import type { RouteLocationRaw, Router } from "vue-router";
import type { Boot, NavigationItem } from "@/boot";
import type { Addresses } from "@/addresses";
import type { ContentEntry } from "@/contents";

/**
 * What one item resolves to. Four shapes, and every kind on the branch is one of them:
 *
 * - `to` — a route in THIS prefix, rendered as a `RouterLink`.
 * - `href` — an absolute URL, rendered as a plain `<a>`, because following it is a full
 *   document load. A `Link` item points off the desk entirely, and a contributed item
 *   whose app said `switches_app` carries a URL the server finished (#42364).
 * - `group` — no destination of its own; it draws whatever names it as `parent_key`.
 * - `expand` — rows that are not known until they are asked for. `Module Contents` is
 *   the only kind of this shape, and the only one whose row count resolution cannot fix.
 *
 * `sidebar` rides alongside a destination rather than being a fifth shape. An item that
 * opens a sidebar is still ordinary navigation — charter point 7 — so it has a real
 * destination and the sidebar key is an annotation on it, which is what lets #42421 mount
 * a panel without this file learning what a panel is.
 */
export type Rendering =
	| { to: RouteLocationRaw; sidebar?: string }
	| { href: string; sidebar?: string }
	| { group: true }
	| { expand: () => Promise<NavigationItem[]> };

/**
 * Everything a renderer is allowed to know. It is a parameter rather than a set of
 * imports on purpose: a contributed renderer lives in another app's repo, and the only
 * module it may import from the framework is `@shell`, which publishes address arithmetic
 * and deliberately nothing else. So what a renderer needs BEYOND an address arrives here,
 * where it is also trivially substitutable in a test.
 */
export type ItemContext = {
	boot: Boot;
	addresses: Addresses;
	/**
	 * The router this document holds. A renderer does not need it — `routeFor` builds every
	 * address there is — but the registry does, to check that what a renderer handed back
	 * actually resolves before `RouterLink` meets it and throws mid-render.
	 */
	router: Router;
	/** Every sidebar in this prefix, keyed by scrubbed address (#42356). */
	sidebars: Record<string, NavigationItem[]>;
	/**
	 * The whole list this item belongs to. `Module Contents` is what needs it: "what is
	 * left of a module" is measured against what the list already shows, and only the
	 * list can answer that.
	 */
	items: NavigationItem[];
	/** The contributed pages this prefix serves — a `Page` item's destination space. */
	pages: { slug: string; title?: string }[];
	/** What a module contains, permission-filtered (`contents.ts`). */
	contentsOf(moduleSlug: string): Promise<ContentEntry[]>;
	/**
	 * Another item's rendering. A `Sidebar` item is the caller: its own destination is the
	 * first destination inside the sidebar it opens, so it has to resolve rows it did not
	 * author. Recursion is depth-guarded by the registry, not by the renderer.
	 */
	renderingOf(item: NavigationItem): Rendering | null;
};

/**
 * A renderer, as an app's `item.js` default-exports it.
 *
 * `render` returning `null` means the item cannot be drawn HERE — a `Module` under a
 * non-modular prefix has no module route to land on — and the rail skips it, the same
 * treatment #42228 chose for a kind with no renderer at all.
 *
 * `label` is the fallback for an item nobody labelled, and only that: an authored label
 * always wins, and is never translated (#42230).
 */
export type ItemRenderer = {
	render(item: NavigationItem, context: ItemContext): Rendering | null;
	label?(item: NavigationItem, context: ItemContext): string | undefined;
};
