// The page an address opens, drawn while its code loads: a declared page, else the standard one.
import { defineAsyncComponent, defineComponent, h, type Component } from "vue";
import { useRoute, type RouteLocationNormalized } from "vue-router";
import type { Addresses } from "@/addresses";
import { replacementFor, standardPage } from "@/contributions/registry";
import FrameSkeleton from "@/shell/FrameSkeleton.vue";
import PageFrame from "@/shell/PageFrame.vue";
import { failedState } from "@/shell/pageState";

type Loaded = { default?: Component } | Component;
type Loader = () => Promise<unknown>;
type Route = Pick<RouteLocationNormalized, "name" | "params">;

// One component per loader, so a render does not create a new component type and remount the page.
const pages = new Map<Loader, Component>();

/** The loader a main address opens and, for a declared page, its props; null on other routes. */
export function mainPageFor(route: Route, addresses: Addresses) {
	const key = route.name;
	const doctype = addresses.doctypeOf(String(route.params.doctype));
	if ((key !== "list" && key !== "record") || !doctype) return null;

	const declared = replacementFor(doctype, key);
	if (!declared) return { loader: standardPage(key), props: null };
	const props = key === "record" ? { doctype, name: String(route.params.name) } : { doctype };
	return { loader: declared.component, props };
}

/** The page a loader gives: the frame's skeleton at once, then the page once its code is in. */
export function loadedPage(loader: Loader) {
	let page = pages.get(loader);
	if (!page) {
		page = framed(loader);
		pages.set(loader, page);
	}
	return page;
}

/** Forgets every loaded page; for tests. */
export function clearLoadedPages() {
	pages.clear();
}

function framed(loader: Loader): Component {
	let loaded = false;
	const page = defineAsyncComponent({
		loader: () =>
			loader().then((module) => {
				loaded = true;
				return pageOf(module as Loaded);
			}),
		loadingComponent: FrameSkeleton,
		errorComponent: defineComponent({
			props: ["error"],
			setup: (props) => () => h(PageFrame, { state: failedState(props.error, reloadAddress) }),
		}),
		delay: 0,
	});
	// The router warns on an async route component, so the routes get a plain one around it.
	return defineComponent({
		name: "LoadedPage",
		setup() {
			const route = useRoute();
			let key: string | undefined;
			return () => {
				// Vue loads a failed page again only on a remount: the key follows the address
				// until the code is in.
				if (!loaded) key = route.path;
				return h(page, { key });
			};
		},
	});
}

// A full reload: the browser can keep a failed module fetch and fail an in-app retry again.
function reloadAddress() {
	window.location.reload();
}

/** A module's default export, read as vue-router reads a lazy route component. */
function pageOf(loaded: Loaded): Component {
	if (typeof loaded === "object" && "default" in loaded && loaded.default) return loaded.default;
	return loaded as Component;
}
