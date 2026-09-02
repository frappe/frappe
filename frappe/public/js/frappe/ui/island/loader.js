/**
 * frappe.ui.mount_island — the one call desk makes to put an app's island on a page.
 *
 *     const island = await frappe.ui.mount_island("insights.dashboard", el, {
 *         props: { dashboard: "sales" },
 *         on: { navigate: (intent) => frappe.set_route(intent.route) },
 *     });
 *     island.update({ filters });
 *     island.unmount();
 *
 * Desk is one host of an island; a frappe-ui app is another. The loop both run —
 * import the module, call its `mount`, keep the handle — is
 * `@framework/ui/island/host`. This file is desk's half: it resolves a name
 * against boot, assembles the desk context, and publishes the `frappe.ui` API.
 *
 * Resolution runs name -> the `ui_islands` registry (hooks, carried in boot) ->
 * assets.json -> the module URL the host loop imports. An island is a
 * self-contained ES module, so this file rides desk's normal esbuild bundle and
 * the page needs nothing loaded ahead of the island itself.
 *
 * The caller passes `{ props, on }`. Desk adds `desk` and `styles`. Everything
 * the island then does with them is the app's own build:
 * ui/island/decisions/0001-an-app-bundles-its-own-island.md.
 */

import {
	mountIsland,
	reloadChangedIslands,
	unmountIsland,
} from "../../../../../../ui/island/host.js";

const ISLAND_JS_SUFFIX = ".island.js";
const ISLAND_CSS_SUFFIX = ".island.css";

/**
 * @param {string} name        Island name as declared in an app's `ui_islands` hook.
 * @param {HTMLElement|JQuery} el
 * @param {{ props?: Object, on?: Object }} [context]
 * @returns {Promise<{ update: (props: Object) => void, unmount: () => void }>}
 */
function mount_island(name, el, context = {}) {
	return mountIsland(name, el, {
		resolve: resolve_island,
		desk: build_desk(),
		props: context.props,
		on: context.on,
	});
}

function resolve_island(name) {
	const bundle = frappe.boot?.ui_islands?.[name];
	if (!bundle) {
		throw new Error(
			`Island "${name}" is not declared. Add it to ui_islands in the app's hooks.py.`
		);
	}

	const assets_json = frappe.boot?.assets_json || {};
	const js = assets_json[bundle + ISLAND_JS_SUFFIX];
	if (!js) {
		throw new Error(
			`Island "${name}" points at bundle "${bundle}", but "${bundle}${ISLAND_JS_SUFFIX}" is not in assets.json. Build the app that ships it.`
		);
	}

	return { js, css: assets_json[bundle + ISLAND_CSS_SUFFIX] || null };
}

/**
 * The ambient context every island receives. The caller never assembles it, so an
 * island honors desk's language and timezone with no per-island wiring. The mount
 * contract adds `theme`, where it can be a tracked read.
 *
 * Everything here is data or a desk call. Nothing in it is a Vue value, because
 * desk's bundle and the island run on separate copies of Vue.
 */
function build_desk() {
	const boot = frappe.boot || {};
	const desk = {
		locale: boot.lang || "en",
		timezone: boot.time_zone?.user || boot.time_zone?.system || null,
		user: frappe.session?.user || boot.user?.name || null,
		base_url: frappe.urllib ? frappe.urllib.get_base_url() : window.location.origin,

		// Ancestors only, for an island that draws its own page header. Desk's
		// breadcrumbs are page-head markup (`page.html`) that such a page does not
		// draw, so the trail reaches the island as data or not at all.
		breadcrumbs: entry_breadcrumbs(),

		// Desk routing, which an island cannot do for itself. The browser
		// retargets a click inside a shadow root to the island's host element, so
		// desk's anchor delegation never matches and a plain link reloads the page.
		navigate: (route) => frappe.set_route(route),

		// Names the browser tab, for an island that is the whole page. Desk keeps
		// the unread count as a title prefix over a remembered original, and it
		// restores that original over any direct write to `document.title`.
		set_title: (title) => frappe.utils.set_title(title),
	};

	return desk;
}

/**
 * One crumb: the workspace the reader was on immediately before this page. Only
 * the previous route counts, the rule `frappe.breadcrumbs.set_workspace` already
 * follows, because a workspace further back is a parent the reader never came
 * through. With no workspace behind this page, the island gets no crumb.
 */
function entry_breadcrumbs() {
	const previous = frappe.route_history?.slice(-2)[0];
	if (!previous || previous[0] !== "Workspaces") return [];

	const is_private = previous[1] === "private";
	const name = is_private ? previous[2] : previous[1];
	if (!name) return [];

	const workspace = frappe.workspaces?.[frappe.router.slug(name)];
	return [
		{
			label: __(workspace?.title || name),
			// The path form, not the ["Workspaces", slug] standard route. Only
			// the path form carries a private workspace's prefix, and it is how
			// the sidebar routes.
			route: frappe.router.slug(is_private ? `private/${name}` : name),
		},
	];
}

frappe.provide("frappe.ui");
frappe.ui.mount_island = mount_island;
frappe.ui.unmount_island = unmountIsland;

if (frappe.boot?.developer_mode) {
	frappe.hot_update = frappe.hot_update || [];
	// A rebuild moves the asset hash, so the islands on the page point at a stale
	// module. Only those whose URL moved are re-mounted.
	frappe.hot_update.push(() => reloadChangedIslands());
}
