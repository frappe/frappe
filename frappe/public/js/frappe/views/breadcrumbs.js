// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// The trail names the entity, never the shell it lives in: the dock names the app and the module
// sidebar names the module and highlights the entity within it, so a workspace crumb would
// repeat what the shell already says. This file therefore does not resolve an entity to a module
// or a workspace; that is `shell_for_route`'s job, and its answer is a shell. See
// ui/sidebar/sidebar.js.
//
// The trail is page-scoped state. Each `frappe.ui.Page` holds its own items and paints them into
// its own page head, so a view can only ever change the trail of the page it was handed, and a
// view that is not on screen paints into markup nobody is looking at. `page.set_breadcrumbs()`
// is the setter; each view inlines its own trail, and this file knows nothing about doctypes,
// layouts, permissions or trees.
//
// What is left here is compatibility for apps outside this one.
frappe.breadcrumbs = {
	/**
	 * Name the page the container is showing.
	 *
	 * Only the `{type: "Custom", label, route}` shape has drawn anything since 8d047d0e98
	 * deleted the home and workspace crumbs in June 2026. `add("Selling")` and
	 * `add(module, doctype)` fed those, so they stay accepted and silent: the module sidebar
	 * draws what they were asking for.
	 *
	 * @param {string|Object} module Module name, or the whole options object
	 * @param {string} [doctype]
	 * @param {string} [type] "Custom" to name the page
	 */
	add(module, doctype, type) {
		const opts =
			typeof module === "object" ? module : { module: module, doctype: doctype, type: type };
		if (opts.type !== "Custom") return;

		frappe.container?.page?.page?.set_breadcrumbs([{ label: opts.label, href: opts.route }]);
	},

	/** Repaint the trail of the page the container is showing. */
	update() {
		frappe.container?.page?.page?.render_breadcrumbs();
	},
};
