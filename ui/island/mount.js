/**
 * `mountVueIsland`: the mount contract an island entry is built on.
 *
 *     import { mountVueIsland } from "@framework/ui/island";
 *     import App from "./App.vue";
 *
 *     export const mount = (el, context) =>
 *         mountVueIsland(el, { ...context, component: App });
 *
 * The entry ships one `mount(el, context)` export. The host loop resolves the
 * island's name, hands over an empty element and the `context` below, and holds
 * the returned handle.
 *
 * A shadow root isolates the island. The boundary encapsulates CSS both ways.
 * The island ships its normal preflight, and nothing crosses into desk's
 * Bootstrap DOM. See decisions/0001-an-app-bundles-its-own-island.md.
 */

import { createApp, h, ref, shallowRef } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { portalTargetKey } from "frappe-ui";

import { hostKey } from "./context.js";
import { currentTheme, onThemeChange } from "./theme.js";

// Desk's modal tier, Bootstrap's `.modal`. It is level with a desk dialog and
// above every page-level control: the icon rail at 1020, menus at 1030.
const OVERLAY_Z_INDEX = "1050";

// url -> Promise<CSSStyleSheet>. One sheet object per URL for the whole page,
// adopted into every shadow root. The browser fetches and parses it once.
const styleSheets = new Map();

/**
 * @typedef {Object} MountVueIslandOptions
 * @property {any} component            Vue component to render.
 * @property {import('./context.js').IslandHost} [host]
 *                                      Ambient host context (host-injected).
 * @property {Object} [props]           Vue's props object: data and `on*`
 *                                      listeners, as `h()` takes them.
 * @property {string[]} [styles]        Stylesheet URLs to adopt, in order
 *                                      (host-injected).
 * @property {(app: any) => void} [configure]  Called with the Vue app before
 *                                      mount, for plugins and global components.
 * @property {Array} [routes]           vue-router routes. Default none.
 */

/**
 * `el` is the empty element the host loop gives this island. The loop owns the
 * target, so nothing here unmounts what it finds there.
 *
 * @param {HTMLElement} el
 * @param {MountVueIslandOptions} options
 * @returns {Promise<{ app: any, shadow_root: ShadowRoot, update: (props: Object) => void, unmount: () => void }>}
 */
export async function mountVueIsland(el, options) {
	const { component, host = {}, props = {}, styles = [], configure, routes } = options || {};

	if (!component) {
		throw new Error("mountVueIsland: no component given");
	}
	if (!el || !el.appendChild) {
		throw new Error("mountVueIsland: mount target is not an element");
	}

	const shadowHost = document.createElement("div");
	shadowHost.className = "frappe-island";
	// The host bounds the box and the island lays out inside it. A percentage
	// height chains through only if both this host and the root below carry it.
	// Against an auto-height target it resolves to auto, so a content-sized
	// island is unchanged.
	shadowHost.style.height = "100%";
	el.appendChild(shadowHost);
	const shadowRoot = shadowHost.attachShadow({ mode: "open" });

	// frappe-ui's dark selector `[data-theme="dark"] .dark\:x` is a descendant
	// rule, so the attribute must sit inside the shadow root. No descendant
	// combinator reaches :host.
	const root = document.createElement("div");
	root.className = "frappe-island-root";
	root.style.height = "100%";

	// Overlays such as Dialog, Popover and Select portal here, not to <body>, so
	// they render inside the styled tree. reka-ui reads its target from an
	// explicit prop first, then from the host inject, then from its own default.
	// Only an element survives the shadow boundary, because the browser queries
	// a selector string against the document.
	const portal = document.createElement("div");
	portal.className = "frappe-island-portal";
	// A shadow root is not a stacking context, so an overlay inside it competes
	// with desk's page-level controls directly. At `z-index: auto` the browser
	// paints the icon rail and desk's menus over the overlay, although the
	// overlay covers them for hit testing. The portal carries the tier, not the
	// host, so the island's content stays in the page flow.
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

	// Theme joins the host context here, because only this side of the boundary
	// can make it a tracked read. A mid-session theme switch then re-renders the
	// island. This is a new object, because the one the host passed is the host's.
	const context = {
		...host,
		get theme() {
			return theme.value;
		},
	};

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

		// frappe-ui components such as Button and MultiSelect always call
		// useRouter(). A memory router keeps that inject resolvable. An island that
		// wants navigation of its own passes real routes.
		app.use(createRouter({ history: createMemoryHistory(), routes: routes || [] }));

		app.provide(portalTargetKey, portal);
		app.provide(hostKey, context);

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
					// A failed unmount must not block the removal of the shadow host.
					console.error("island: error during unmount", e);
				}
				// Drops the shadow root and everything in it.
				shadowHost.remove();
			},
		};

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
