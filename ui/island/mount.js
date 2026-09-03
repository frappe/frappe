/**
 * `mountVueIsland` — the mount contract an island entry is built on.
 *
 *     import { mountVueIsland } from "@framework/ui/island";
 *     import App from "./App.vue";
 *
 *     export const mount = (el, context) =>
 *         mountVueIsland(el, { ...context, component: App });
 *
 * The entry ships one `mount(el, context)` export. Desk calls it through
 * `frappe.ui.mount_island`, which resolves the island's name and hands over the
 * `context` below.
 *
 * A shadow root isolates the island. The boundary encapsulates CSS both ways, so
 * the island ships its normal preflight and nothing crosses into desk's
 * Bootstrap DOM. See decisions/0001-an-app-bundles-its-own-island.md.
 */

import { createApp, h, ref, shallowRef } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { portalTargetKey } from "frappe-ui";

import { currentTheme, onThemeChange } from "./theme.js";

/**
 * Injection key for the ambient desk context. `Symbol.for`, so an island that
 * carries its own copy of this module still reads what the host provided.
 */
export const deskKey = Symbol.for("frappe:island-desk");

// Desk's modal tier (Bootstrap's `.modal`), level with a desk dialog and above
// every page-level control desk paints: the icon rail at 1020, menus at 1030.
const OVERLAY_Z_INDEX = "1050";

// url -> Promise<CSSStyleSheet>. One sheet object per URL for the whole page,
// adopted into every shadow root. Fetched once and parsed once.
const styleSheets = new Map();

// target element -> handle. A second mount into an element replaces the first.
const mounted = new WeakMap();

/**
 * @typedef {Object} IslandDesk
 * @property {string} [locale]
 * @property {string|null} [timezone]
 * @property {string|null} [user]
 * @property {string} [base_url]
 * @property {(route: string) => void} [navigate]  route the host to one of its
 *           own pages
 * @property {string} [theme]  the host's live theme, added by `mountVueIsland`
 */

/**
 * @typedef {Object} MountVueIslandOptions
 * @property {any} component            Vue component to render.
 * @property {IslandDesk} [desk]        Ambient desk context (host-injected).
 * @property {Object} [props]           Vue's props object: data and `on*`
 *                                      listeners, as `h()` takes them.
 * @property {string[]} [styles]        Stylesheet URLs to adopt, in order
 *                                      (host-injected).
 * @property {(app: any) => void} [configure]  Called with the Vue app before
 *                                      mount, for plugins and global components.
 * @property {Array} [routes]           vue-router routes. Default none.
 */

/**
 * @param {HTMLElement|JQuery} el
 * @param {MountVueIslandOptions} options
 * @returns {Promise<{ app: any, shadow_root: ShadowRoot, update: (props: Object) => void, unmount: () => void }>}
 */
export async function mountVueIsland(el, options) {
	const { component, desk = {}, props = {}, styles = [], configure, routes } = options || {};

	const target = resolveElement(el);
	if (!component) {
		throw new Error("mountVueIsland: no component given");
	}

	mounted.get(target)?.unmount();

	const shadowHost = document.createElement("div");
	shadowHost.className = "frappe-island";
	// The host bounds the box and the island lays out inside it. A percentage
	// height chains through only if both this host and the root below carry it.
	// Against an auto-height target it resolves to auto, so a content-sized
	// island is unchanged.
	shadowHost.style.height = "100%";
	target.appendChild(shadowHost);
	const shadowRoot = shadowHost.attachShadow({ mode: "open" });

	// frappe-ui's dark selector `[data-theme="dark"] .dark\:x` is a descendant
	// rule, so the attribute must sit inside the shadow root. No descendant
	// combinator reaches :host.
	const root = document.createElement("div");
	root.className = "frappe-island-root";
	root.style.height = "100%";

	// Overlays (Dialog, Popover, Select, …) portal here, not to <body>, so they
	// render inside the styled tree. reka-ui resolves its target as explicit prop
	// > host inject > its own default. Only an element survives the shadow
	// boundary. The browser queries a selector string against the document.
	const portal = document.createElement("div");
	portal.className = "frappe-island-portal";
	// A shadow root is not a stacking context, so an overlay inside it competes
	// with desk's chrome directly. At `z-index: auto` the browser paints the icon
	// rail (1020) and desk's menus (1030) over the overlay, although the overlay
	// covers them for hit testing. The portal carries the tier, not the host, so
	// the island's content stays in the page flow.
	portal.style.position = "relative";
	portal.style.zIndex = OVERLAY_Z_INDEX;

	shadowRoot.append(root, portal);

	const applyTheme = (theme) => {
		root.setAttribute("data-theme", theme);
		portal.setAttribute("data-theme", theme);
	};
	applyTheme(currentTheme());

	const theme = ref(currentTheme());
	const stopTheme = onThemeChange((next) => {
		theme.value = next;
		applyTheme(next);
	});

	// Theme joins the desk context here, because only this side of the boundary
	// can make it a tracked read — a mid-session theme switch then re-renders the
	// island. A getter, because consumers hold the context by reference.
	Object.defineProperty(desk, "theme", {
		configurable: true,
		enumerable: true,
		get: () => theme.value,
	});

	try {
		return await build();
	} catch (e) {
		// The shadow host is in the page already, so a failed stylesheet fetch or
		// a throwing component would leave an empty island behind.
		stopTheme();
		shadowHost.remove();
		throw e;
	}

	async function build() {
		// In order, so a sheet later in the list wins ties.
		shadowRoot.adoptedStyleSheets = await Promise.all(styles.map(sharedStyleSheet));

		const currentProps = shallowRef({ ...props });

		const app = createApp({
			name: "FrappeIsland",
			render: () => h(component, currentProps.value),
		});

		// Desk globals, so components that call `__()` or read `frappe` work.
		window.SetVueGlobals?.(app);

		// frappe-ui components (Button, MultiSelect, …) call useRouter() always. A
		// memory router keeps that inject resolvable. An island that wants
		// navigation of its own passes real routes.
		app.use(createRouter({ history: createMemoryHistory(), routes: routes || [] }));

		app.provide(portalTargetKey, portal);
		app.provide(deskKey, desk);

		configure?.(app);

		app.mount(root);

		let destroyed = false;
		const handle = {
			app,
			shadow_root: shadowRoot,
			update(next) {
				if (destroyed) return;
				currentProps.value = { ...currentProps.value, ...next };
			},
			unmount() {
				if (destroyed) return;
				destroyed = true;
				stopTheme();
				try {
					app.unmount();
				} catch (e) {
					// A failed unmount must not block teardown of the host.
					console.error("island: error during unmount", e);
				}
				// Drops the shadow root and everything in it.
				shadowHost.remove();
				if (mounted.get(target) === handle) mounted.delete(target);
			},
		};

		mounted.set(target, handle);
		return handle;
	}
}

function sharedStyleSheet(url) {
	if (!styleSheets.has(url)) {
		const sheet = fetch(url)
			.then((response) => {
				if (!response.ok) {
					throw new Error(`island: cannot load ${url} (${response.status})`);
				}
				return response.text();
			})
			.then((css) => {
				const sheet = new CSSStyleSheet();
				sheet.replaceSync(css);
				return sheet;
			})
			.catch((e) => {
				// One failed fetch must not poison every later mount.
				styleSheets.delete(url);
				throw e;
			});
		styleSheets.set(url, sheet);
	}
	return styleSheets.get(url);
}

function resolveElement(el) {
	const target = el && el.jquery ? el[0] : el;
	if (!target || !target.appendChild) {
		throw new Error("island: mount target is not an element");
	}
	return target;
}
