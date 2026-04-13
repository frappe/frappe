/**
 * frappe-ui POC – Desk Vue island bundle entry.
 *
 * This file is compiled by the Frappe esbuild pipeline into
 * `frappe_ui_poc.bundle.{hash}.js`.
 *
 * Companion CSS is declared in `frappe_ui_poc.bundle.css` (same directory)
 * and loaded via frappe.require alongside this JS bundle.
 *
 * Import strategy
 * ───────────────
 * We import from `frappe-ui/desk` which resolves to the pre-compiled
 * `dist/desk/index.js` artifact inside the local `frappe-ui` package.
 * This keeps Vite virtual module resolution (like `~icons/lucide/*`)
 * away from the esbuild pipeline entirely.
 */

import { createApp } from "vue";
import { createRouter, createMemoryHistory } from "vue-router";
import FrappeUIPocComponent from "./FrappeUIPoc.vue";

class FrappeUIPoc {
	constructor({ wrapper, page }) {
		this.$wrapper = wrapper;
		this.page = page;
		this.init();
	}

	init() {
		this.page.set_title(__("frappe-ui POC"));
		this.setup_app();
	}

	setup_app() {
		// Create a dedicated mount point inside the page section.
		const mount = document.createElement("div");
		mount.setAttribute("data-frappe-ui", "");
		mount.setAttribute("data-theme", "light");
		this.$wrapper[0].appendChild(mount);

		// Create a portal container for Dialog overlays.
		// Dialogs use Vue's Teleport internally (via reka-ui's DialogPortal).
		// By teleporting into this container instead of <body> we ensure that:
		//  1. Tailwind utilities scoped to [data-frappe-ui] apply to dialog DOM.
		//  2. Bootstrap element-selector rules (button {}, h3 {}, p {}) are
		//     overridden by the higher-specificity [data-frappe-ui] + class
		//     selectors Tailwind emits when important: '[data-frappe-ui]' is set.
		const portalId = `frappe-ui-portal-${Math.random().toString(36).slice(2, 7)}`;
		const portal = document.createElement("div");
		portal.id = portalId;
		portal.setAttribute("data-frappe-ui", "");
		portal.setAttribute("data-theme", "light");
		document.body.appendChild(portal);
		// Remove the portal from the DOM when the app unmounts.
		this._portalEl = portal;

		const app = createApp(FrappeUIPocComponent);

		// Re-use Desk globals (__, frappe) so components that call them work.
		SetVueGlobals(app);

		// frappe-ui components (Button) use useRouter() internally.
		// Install a minimal memory router so the inject() call resolves
		// without throwing. No routes needed since we don't navigate.
		const router = createRouter({
			history: createMemoryHistory(),
			routes: [],
		});
		app.use(router);

		// Tell frappe-ui's Dialog component which portal container to use.
		// Dialog.vue injects 'frappe-ui:dialog-portal-target' and passes it to
		// reka-ui's <DialogPortal :to>, ensuring overlay DOM lives inside
		// [data-frappe-ui] where Tailwind's scoped utilities apply.
		app.provide("frappe-ui:dialog-portal-target", `#${portalId}`);

		app.mount(mount);
	}
}

// Expose via frappe.ui so the page controller can instantiate it.
frappe.provide("frappe.ui");
frappe.ui.FrappeUIPoc = FrappeUIPoc;
