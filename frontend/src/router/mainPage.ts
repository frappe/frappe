// The page a main list or record address opens: an app's declared page, else the standard one.
import { defineAsyncComponent, type Component } from "vue";
import type { RouteLocationNormalized } from "vue-router";
import type { Addresses } from "@/addresses";
import { replacementFor } from "@/contributions/registry";
import { standardPages } from "./standardPages";

type Loaded = { default?: Component } | Component;
type Loader = () => Promise<unknown>;
type Route = Pick<RouteLocationNormalized, "name" | "params">;

// One component per loader, so a render does not create a new component type and remount the page.
const pages = new Map<Loader, Component>();
// A page rendered before its preload; kept apart so the preload still loads the real one.
const fallbacks = new Map<Loader, Component>();

/** The loader a main address opens and, for a declared page, its props; null on other routes. */
export function mainPageFor(route: Route, addresses: Addresses) {
	const key = route.name;
	const doctype = addresses.doctypeOf(String(route.params.doctype));
	if ((key !== "list" && key !== "record") || !doctype) return null;

	const declared = replacementFor(doctype, key);
	if (!declared) return { loader: standardPages[key], props: null };
	const props = key === "record" ? { doctype, name: String(route.params.name) } : { doctype };
	return { loader: declared.component, props };
}

/** Loads the page before the navigation confirms, so a failed import fails the navigation. */
export async function preloadMainPage(route: Route, addresses: Addresses) {
	const loader = mainPageFor(route, addresses)?.loader;
	if (!loader || pages.has(loader)) return;
	pages.set(loader, pageOf((await loader()) as Loaded));
	fallbacks.delete(loader);
}

/** The preloaded page, or one that loads itself when no preload ran. */
export function loadedPage(loader: Loader) {
	const page = pages.get(loader);
	if (page) return page;
	let fallback = fallbacks.get(loader);
	if (!fallback) {
		fallback = defineAsyncComponent(() => loader().then((loaded) => pageOf(loaded as Loaded)));
		fallbacks.set(loader, fallback);
	}
	return fallback;
}

/** Forgets every loaded page; for tests. */
export function clearLoadedPages() {
	pages.clear();
	fallbacks.clear();
}

/** A module's default export, read as vue-router reads a lazy route component. */
function pageOf(loaded: Loaded): Component {
	if (typeof loaded === "object" && "default" in loaded && loaded.default) return loaded.default;
	return loaded as Component;
}
