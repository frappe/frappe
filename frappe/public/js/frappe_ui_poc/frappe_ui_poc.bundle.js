/**
 * frappe-ui POC — Desk Vue island entry.
 *
 * Compiled by Frappe's esbuild pipeline into
 *   `frappe_ui_poc.bundle.{hash}.js` (loaded by the page controller).
 *
 * The companion CSS lives in `frappe_ui_poc.bundle.css` in the same folder.
 *
 * All the mount/portal/router/SetVueGlobals/hot-reload boilerplate lives in
 * `frappe.ui.mount_vue_island` (frappe/public/js/frappe/ui/vue_island.js).
 * This file just wires up the page-controller entry point.
 */

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
