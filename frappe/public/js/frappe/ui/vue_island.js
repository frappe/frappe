/**
 * frappe.ui.mount_vue_island — convenience helper for mounting a Vue 3
 * component as a Desk island that uses frappe-ui.
 *
 * What this collapses
 * ───────────────────
 * Without this helper, every new frappe-ui-based Desk page has to repeat:
 *   • Create an inner mount element with `data-frappe-ui` + `data-theme`.
 *   • Create a body-level portal element with the same attrs (so Dialog
 *     overlays and reka-ui popovers teleport inside the styled scope).
 *   • `createApp(component)` + `SetVueGlobals(app)`.
 *   • Install a memory-history vue-router so `useRouter()` calls don't
 *     throw (frappe-ui's Button etc. call it unconditionally).
 *   • `app.provide('frappe-ui:portal-target', ...)` so frappe-ui's Dialog
 *     teleports into the styled portal instead of bare <body>.
 *   • Tear all of that down on page leave AND on hot reload.
 *
 * The helper does all of it. A frappe-ui-based island bundle becomes:
 *
 *     import MyComponent from "./MyComponent.vue";
 *     import { mountVueIsland } from "frappe/public/js/frappe/ui/vue_island.js";
 *
 *     frappe.provide("frappe.ui");
 *     frappe.ui.mount_my_island = (opts) =>
 *         mountVueIsland({ ...opts, component: MyComponent });
 *
 * Hot reload
 * ──────────
 * The helper keeps a WeakMap of wrapper-element → mounted-app. If you call
 * it again with the same wrapper, the previous app is `.unmount()`ed and
 * its portal element removed before the new one is created. That makes
 * `frappe.hot_update`-driven soft reloads safe: re-running the bundle's
 * `frappe.require(...)` chain (which is what `build_events` already does
 * after a successful esbuild rebuild) cleanly swaps the live app in
 * place, with no leaked Vue instances or piled-up <script> tags.
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

	// Inner mount root — Tailwind's `important: '[data-frappe-ui]'` makes
	// every utility rule fire only inside this attribute, so the island's
	// styles cannot leak outward into Bootstrap-owned Desk DOM.
	const mountEl = document.createElement("div");
	mountEl.setAttribute("data-frappe-ui", "");
	mountEl.setAttribute("data-theme", "light");
	mountEl.className = "frappe-ui-island";
	wrapperEl.appendChild(mountEl);

	// Body-level portal for Dialog overlays + reka-ui popovers.
	//
	// Overlay components (Dialog, Popover, Combobox, Select, MultiSelect,
	// Dropdown, Tooltip, TimePicker, date pickers) teleport their content out
	// of the normal DOM tree via reka-ui `<*Portal>`. Without a styled portal
	// it lands at bare <body> — outside any `[data-frappe-ui]` ancestor — so
	// our scoped utility classes don't apply and Bootstrap CSS bleeds in.
	//
	// Every such component resolves its teleport target as
	//   explicit prop → usePortalTarget() inject → reka-ui default (<body>)
	// via frappe-ui's `usePortalTarget()` composable, whose injection key is the
	// plain string `frappe-ui:portal-target`. Providing that key below routes
	// all overlays into this styled portal element.
	const portalId = `frappe-ui-portal-${Math.random().toString(36).slice(2, 9)}`;
	const portalEl = document.createElement("div");
	portalEl.id = portalId;
	portalEl.setAttribute("data-frappe-ui", "");
	portalEl.setAttribute("data-theme", "light");
	document.body.appendChild(portalEl);

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

	// Portal target consumed by frappe-ui's usePortalTarget() (string key, no
	// Symbol). reka-ui's `:to` accepts a CSS selector, so `#<portalId>` resolves
	// to the styled portal element appended above.
	app.provide("frappe-ui:portal-target", `#${portalId}`);

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
		if (portalEl.parentNode) portalEl.parentNode.removeChild(portalEl);
		if (mountEl.parentNode) mountEl.parentNode.removeChild(mountEl);
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
