/**
 * frappe-ui POC — Desk Vue island entry.
 *
 * Built by Frappe's Vite islands pipeline (esbuild/build-islands.mjs) into
 * `js/frappe_ui_poc.bundle.[hash].js` with a companion
 * `css/frappe_ui_poc.bundle.[hash].css`. Both are registered in assets.json
 * (keys `frappe_ui_poc.bundle.js` / `frappe_ui_poc.bundle.css`) and loaded by
 * the page controller via `frappe.require`, exactly like a legacy bundle.
 *
 * Island entries live under `frappe/public/js/islands/` — a directory the
 * esbuild pipeline ignores — so this `.bundle.js` is built by Vite (which
 * compiles frappe-ui from source) instead of esbuild.
 *
 * The island imports its own CSS so Vite emits the stylesheet as a side-effect
 * asset — no separate CSS entry. All the mount/portal/router/SetVueGlobals/
 * hot-reload boilerplate lives in `frappe.ui.mount_vue_island`
 * (frappe/public/js/frappe/ui/vue_island.js).
 */

import "./frappe_ui_poc.bundle.css";
import FrappeUIPocComponent from "./FrappeUIPoc.vue";
import { mountVueIsland } from "frappe/public/js/frappe/ui/vue_island.js";

frappe.provide("frappe.ui");

frappe.ui.FrappeUIPoc = function ({ wrapper, page }) {
	return mountVueIsland({
		wrapper,
		page,
		component: FrappeUIPocComponent,
		title: __("frappe-ui POC"),
		bundleName: "frappe_ui_poc.bundle.js",
	});
};
