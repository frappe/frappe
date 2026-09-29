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

// Deprecated members, kept so an app written against the old module keeps running.
// Marked 2026-09-29, for removal in v17. Each one warns once and changes nothing.
//
// What to use instead. Every replacement is a method on the page you own, which you reach as
// `wrapper.page` inside a desk page, `frm.page` on a form, or `this.page` in a view:
//
//   all, current_page()          the trail is no longer a registry keyed by route, so there is
//                                nothing to read or write. Hold your own items instead.
//   clear(), $breadcrumbs        page.set_breadcrumbs([]) empties your page's trail. Writing
//                                markup into a shared node is what this replaces.
//   append_breadcrumb_element()  page.set_breadcrumbs([...items, { label, href }])
//   set_custom_breadcrumbs()     page.set_breadcrumbs([{ label, href }])
//   set_tree_breadcrumb()        page.set_breadcrumbs([{ label, href }])
//   set_list_breadcrumb()        page.set_breadcrumbs([{ label, href }])
//   set_form_breadcrumb()        frappe.ui.form.get_breadcrumbs(frm)
//   set_dashboard_breadcrumb()   page.set_breadcrumbs([...items, { label }])
//   rename(), toggle()           nothing. The trail is redrawn from the page that owns it.
const warned = new Set();

function deprecated(name, advice) {
	if (warned.has(name)) return;
	warned.add(name);
	console.warn(
		`\`frappe.breadcrumbs.${name}\` is deprecated and has no effect on the trail. ` +
			`It is marked for removal in v17. ${advice}`
	);
}

const OWN_PAGE = "Use `page.set_breadcrumbs(items)` on the page you own.";
const NO_LONGER_KEYED =
	"The trail is no longer a registry keyed by route; hold your own items instead.";

Object.assign(frappe.breadcrumbs, {
	clear: () => deprecated("clear", "Use `page.set_breadcrumbs([])` on the page you own."),
	rename: () => deprecated("rename", "The trail is redrawn from the page that owns it."),
	toggle: () => deprecated("toggle", "The trail follows the page that owns it."),
	append_breadcrumb_element: () => deprecated("append_breadcrumb_element", OWN_PAGE),
	set_custom_breadcrumbs: () => deprecated("set_custom_breadcrumbs", OWN_PAGE),
	set_tree_breadcrumb: () => deprecated("set_tree_breadcrumb", OWN_PAGE),
	set_list_breadcrumb: () => deprecated("set_list_breadcrumb", OWN_PAGE),
	set_dashboard_breadcrumb: () => deprecated("set_dashboard_breadcrumb", OWN_PAGE),
	set_form_breadcrumb: () =>
		deprecated("set_form_breadcrumb", "Use `frappe.ui.form.get_breadcrumbs(frm)`."),

	current_page() {
		deprecated("current_page", NO_LONGER_KEYED);
		return frappe.get_route_str();
	},
});

// `all` was read and written as `all[route_str]`, and `$breadcrumbs` was appended to. Both
// answer with something inert so neither pattern throws.
const dumpster = {};
let $detached = null;

Object.defineProperty(frappe.breadcrumbs, "all", {
	get() {
		deprecated("all", NO_LONGER_KEYED);
		return dumpster;
	},
});

Object.defineProperty(frappe.breadcrumbs, "$breadcrumbs", {
	get() {
		deprecated("$breadcrumbs", OWN_PAGE);
		// detached, so anything written here lands nowhere rather than in a shared node
		return ($detached = $detached || $("<ul>"));
	},
});
