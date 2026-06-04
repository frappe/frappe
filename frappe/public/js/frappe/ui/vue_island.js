/**
 * frappe.ui.mount_vue_island — convenience helper for mounting a Vue 3
 * component as a Desk island that uses frappe-ui.
 *
 * Isolation: Shadow DOM
 * ─────────────────────
 * Each island mounts inside a shadow root. The shadow boundary encapsulates CSS
 * both ways, so frappe-ui ships its normal full Tailwind + preflight and nothing
 * leaks in or out of Bootstrap-owned Desk DOM — no `[data-frappe-ui]` scoping,
 * no `!important` stamping, no scoped preflight.
 *
 * What this helper collapses
 * ──────────────────────────
 * Without it, every new frappe-ui-based Desk page would repeat:
 *   • Create a host element, `attachShadow`, and a mount root inside it.
 *   • Inject the island's stylesheet INTO the shadow root (a head <link>
 *     wouldn't reach it).
 *   • Create a teleport target inside the shadow and `app.provide(
 *     'frappe-ui:portal-target', el)` so reka-ui overlays (Dialog, Popover,
 *     Combobox, …) render inside the styled, encapsulated tree, not at <body>.
 *   • `createApp(component)` + `SetVueGlobals(app)`.
 *   • Install a memory-history vue-router so `useRouter()` calls don't throw
 *     (frappe-ui's Button etc. call it unconditionally).
 *   • Tear all of that down on page leave AND on hot reload.
 *
 * A frappe-ui-based island bundle becomes:
 *
 *     import MyComponent from "./MyComponent.vue";
 *     import { mountVueIsland } from "frappe/public/js/frappe/ui/vue_island.js";
 *
 *     frappe.provide("frappe.ui");
 *     frappe.ui.mount_my_island = (opts) =>
 *         mountVueIsland({ ...opts, component: MyComponent,
 *                          styleBundles: ["my_island.bundle.css"] });
 *
 * Hot reload
 * ──────────
 * The helper keeps a WeakMap of wrapper-element → mounted-app. Re-calling it
 * with the same wrapper unmounts the previous app and removes its host (and
 * with it the shadow root, styles, and portal). That makes
 * `frappe.hot_update`-driven soft reloads safe: re-running the bundle's
 * `frappe.require(...)` chain cleanly swaps the live app in place, with no
 * leaked Vue instances or piled-up shadow hosts.
 */

import { createApp } from "vue";
import { createRouter, createMemoryHistory } from "vue-router";

// wrapper element → { app, mountEl, portalEl, hotUpdateCallback }
const _mounted = new WeakMap();

/**
 * @typedef {Object} MountVueIslandOptions
 * @property {HTMLElement|JQuery} wrapper   Container element. The mount root
 *                                          is created as a child of this.
 * @property {Object} [page]                Frappe page controller. If given,
 *                                          its `set_title(title)` is called.
 * @property {any} component                Vue component (SFC default export).
 * @property {string} [title]               Page title.
 * @property {Object} [props]               Props for the root component.
 * @property {Object} [provide]             Extra app-level provides.
 * @property {string[]} [styleBundles]      Logical assets.json names of CSS
 *                                          bundles (e.g. "foo.bundle.css") to
 *                                          inject into the island's shadow root.
 * @property {Array}  [routes]              Optional vue-router routes;
 *                                          default = [] (memory history).
 * @property {string} [bundleName]          If passed, the helper registers a
 *                                          `frappe.hot_update` callback that
 *                                          re-runs `frappe.require([bundleName])`
 *                                          on the next successful build so the
 *                                          island soft-reloads.
 */

/**
 * Mount a Vue 3 component as a Desk island.
 *
 * @param {MountVueIslandOptions} opts
 * @returns {{ app: import('vue').App, unmount: () => void }}
 */
export function mountVueIsland(opts) {
	const {
		wrapper,
		page,
		component,
		title,
		props,
		provide: extra_provide,
		routes,
		bundleName,
		styleBundles,
	} = opts;

	const $wrapper = wrapper && wrapper.jquery ? wrapper : $(wrapper);
	const wrapperEl = $wrapper[0];
	if (!wrapperEl) {
		throw new Error("mountVueIsland: wrapper element not found");
	}

	// If something was already mounted here (page revisit, hot reload),
	// tear it down first so we don't leak Vue apps or portal elements.
	const prev = _mounted.get(wrapperEl);
	if (prev) prev._tearDown();

	if (title && page && typeof page.set_title === "function") {
		page.set_title(title);
	}

	// Reset the wrapper so we always mount into a clean slate.
	$wrapper.empty();

	// SHADOW DOM ISOLATION
	// --------------------
	// The island lives inside a shadow root, which encapsulates CSS both ways:
	// frappe-ui's full Tailwind + preflight can't leak out into Bootstrap-owned
	// Desk DOM, and Bootstrap can't bleed in. This removes the entire CSS-war
	// (no `[data-frappe-ui]` scoping, no scoped-preflight, no !important stamp).
	const host = document.createElement("div");
	host.className = "frappe-ui-island-host";
	wrapperEl.appendChild(host);
	const shadow = host.attachShadow({ mode: "open" });

	// Inject the island's stylesheet(s) INTO the shadow root (a head <link>
	// wouldn't reach the shadow tree). styleBundles are logical assets.json
	// names (e.g. "foo.bundle.css") resolved to hashed URLs.
	for (const bundle of styleBundles || []) {
		const href = frappe.assets.bundled_asset(bundle);
		const link = document.createElement("link");
		link.rel = "stylesheet";
		link.href = href;
		shadow.appendChild(link);
	}

	// Mount root inside the shadow. `data-theme` drives the design-token theme.
	const mountEl = document.createElement("div");
	mountEl.setAttribute("data-theme", "light");
	mountEl.className = "frappe-ui-island";
	shadow.appendChild(mountEl);

	// Teleport target ALSO inside the shadow root, so reka-ui `<*Portal>`
	// overlays (Dialog, Popover, Combobox, Select, …) render inside the styled,
	// encapsulated tree instead of at bare <body>. Every overlay resolves its
	// target as explicit prop → usePortalTarget() inject → reka default; we
	// provide the inject below. reka-ui's `:to` accepts an element, which (unlike
	// a `#id` selector) resolves correctly across the shadow boundary.
	const portalEl = document.createElement("div");
	portalEl.setAttribute("data-theme", "light");
	portalEl.className = "frappe-ui-island-portal";
	shadow.appendChild(portalEl);

	const app = createApp(component, props || {});

	// Re-use Desk globals so components that read `__()` or `frappe` work.
	if (typeof window.SetVueGlobals === "function") {
		window.SetVueGlobals(app);
	}

	// Several frappe-ui components (Button, MultiSelect, …) call
	// `useRouter()` unconditionally. Install a no-route memory router so
	// inject() resolves without throwing. Callers can pass real routes if
	// they want navigation inside the island.
	const router = createRouter({
		history: createMemoryHistory(),
		routes: routes || [],
	});
	app.use(router);

	// Portal target consumed by frappe-ui's usePortalTarget(). We provide the
	// actual element (not a selector) because it lives inside the shadow root,
	// where a document-level `querySelector('#id')` would never find it.
	app.provide("frappe-ui:portal-target", portalEl);

	if (extra_provide) {
		for (const key of Object.keys(extra_provide)) {
			app.provide(key, extra_provide[key]);
		}
	}

	app.mount(mountEl);

	// Optional soft hot-reload integration.
	//
	// When the user edits a .vue file, esbuild rebuilds the bundle and
	// `build_events.bundle.js` fires `frappe.hot_update` callbacks. We
	// register one that re-requires this bundle. Re-requiring re-runs the
	// bundle's top-level code (which calls mountVueIsland again with the
	// same wrapper) — and the wrapper-keyed teardown above swaps the live
	// app in place without a full page reload.
	let hotUpdateCallback = null;
	if (bundleName && frappe.boot && frappe.boot.developer_mode) {
		hotUpdateCallback = () => {
			if (!document.body.contains(wrapperEl)) {
				// Wrapper was detached (page navigated away). Clean up and
				// stop listening.
				_unregisterHotUpdate(hotUpdateCallback);
				const m = _mounted.get(wrapperEl);
				if (m) m._tearDown();
				return;
			}
			frappe.require(bundleName);
		};
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(hotUpdateCallback);
	}

	function _tearDown() {
		try {
			app.unmount();
		} catch (e) {
			// Swallow — unmount errors shouldn't block a clean rebuild.
			console.error("mountVueIsland: error during unmount", e);
		}
		// Removing the host drops the shadow root and everything in it (mount
		// root, portal, injected stylesheets).
		if (host.parentNode) host.parentNode.removeChild(host);
		if (hotUpdateCallback) _unregisterHotUpdate(hotUpdateCallback);
		_mounted.delete(wrapperEl);
	}

	const handle = { app, _tearDown };
	_mounted.set(wrapperEl, handle);

	return {
		app,
		unmount: _tearDown,
	};
}

function _unregisterHotUpdate(cb) {
	if (!Array.isArray(frappe.hot_update)) return;
	const idx = frappe.hot_update.indexOf(cb);
	if (idx >= 0) frappe.hot_update.splice(idx, 1);
}

// Expose on the frappe global as well so non-ESM callers (e.g. inline page
// scripts during transition) can use it without an import.
if (typeof frappe !== "undefined") {
	frappe.provide("frappe.ui");
	frappe.ui.mount_vue_island = mountVueIsland;
}
