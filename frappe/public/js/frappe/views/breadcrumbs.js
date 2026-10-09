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
// is the setter, and every view in this app uses it.
//
// Everything below is the compatibility layer for apps written against the old module. It still
// works, rather than merely not throwing: each member forwards to the page on screen. Two things
// make that safe where the old module was not. Writes land on one page instead of every cached
// page at once, because there is no longer a `$(".navbar-breadcrumbs")` selector. And this app's
// own views no longer come through here, so an off-screen form cannot reach the trail by
// accident; only an explicit call from outside does, which is what it asked for.
//
// Marked 2026-09-29, for removal in v17. Each member warns once and names its replacement.

frappe.breadcrumbs = {
	/**
	 * Name the page on screen.
	 *
	 * @param {string|Object} module Module name, or the whole options object
	 * @param {string} [doctype]
	 * @param {string} [type] "Custom" for a `{label, route}` crumb
	 */
	add(module, doctype, type) {
		const source =
			typeof module === "object" ? module : { module: module, doctype: doctype, type: type };

		this.all[frappe.get_route_str()] = source;
		this.update();
	},

	/** Repaint the trail of the page on screen. */
	update() {
		frappe.get_current_page()?.render_breadcrumbs();
	},

	/** The route the legacy registry is keyed by. */
	current_page() {
		deprecated("current_page", "`frappe.get_current_page()` for the page itself.");
		return frappe.get_route_str();
	},

	/** Empty the trail of the page on screen. */
	clear() {
		deprecated("clear", "`frappe.get_current_page().set_breadcrumbs([])`.");
		const page = frappe.get_current_page();
		if (!page) return;
		page.legacy_breadcrumbs = null;
		page.set_breadcrumbs([]);
	},

	/**
	 * Show or hide the trail on the page on screen. The old member set a `no-breadcrumbs` class
	 * that no stylesheet read, and it set it the wrong way round; `show` now means show.
	 *
	 * @param {boolean} show
	 */
	toggle(show) {
		deprecated("toggle", "`page.show_breadcrumbs = false`.");
		const page = frappe.get_current_page();
		if (!page) return;
		page.show_breadcrumbs = !!show;
		page.render_breadcrumbs();
	},

	/**
	 * Move a form's registry entry to the renamed document, then repaint. The trail itself is
	 * rebuilt from the route, so the repaint is what actually updates it.
	 */
	rename(doctype, old_name, new_name) {
		deprecated("rename", "nothing; the trail is rebuilt from the route.");
		const old_key = ["Form", doctype, old_name].join("/");
		const new_key = ["Form", doctype, new_name].join("/");
		if (this.all[old_key]) {
			this.all[new_key] = this.all[old_key];
			delete this.all[old_key];
		}
		this.update();
	},

	/**
	 * Append one crumb to the page on screen.
	 *
	 * @param {string} route
	 * @param {string} label
	 */
	append_breadcrumb_element(route, label) {
		deprecated("append_breadcrumb_element", "`page.set_breadcrumbs(items)`.");
		append_items([{ label: label, href: route }]);
	},

	set_custom_breadcrumbs(breadcrumbs) {
		deprecated("set_custom_breadcrumbs", "`page.set_breadcrumbs(items)`.");
		append_items([{ label: breadcrumbs.label, href: breadcrumbs.route }]);
	},

	set_list_breadcrumb(breadcrumbs) {
		deprecated("set_list_breadcrumb", "`page.set_breadcrumbs(items)`.");
		append_items(this.list_items(breadcrumbs));
	},

	set_tree_breadcrumb(breadcrumbs) {
		deprecated("set_tree_breadcrumb", "`page.set_breadcrumbs(items)`.");
		append_items(this.tree_items(breadcrumbs));
	},

	set_form_breadcrumb(breadcrumbs, view) {
		deprecated("set_form_breadcrumb", "`frappe.ui.form.get_breadcrumbs(frm)`.");
		append_items(this.form_items(breadcrumbs, view));
	},

	set_dashboard_breadcrumb(breadcrumbs) {
		deprecated("set_dashboard_breadcrumb", "`page.set_breadcrumbs(items)`.");
		append_items(this.dashboard_items(breadcrumbs));
	},

	/**
	 * Turn a legacy `add()` payload into espresso breadcrumb items, reading the route and the
	 * loaded doc the way `update()` always has. Only the compatibility path reaches this; the
	 * views in this app pass their items directly.
	 *
	 * @param {Object} source
	 * @returns {Array<Object>} items for `frappe.ui.breadcrumbs`
	 */
	resolve(source) {
		if (!source) return [];
		if (source.type === "Custom") {
			return [{ label: source.label, href: source.route }];
		}

		const view = (frappe.get_route()[0] || "").toLowerCase();
		if (source.doctype && ["print", "form"].includes(view)) {
			return [...this.list_items(source), ...this.form_items(source, view)];
		}
		if (source.doctype && view === "tree") {
			return this.tree_items(source);
		}
		if (source.doctype && view === "list") {
			return [...this.list_items(source), ...this.layout_items(source)];
		}
		if (source.doctype && view === "dashboard-view") {
			return [...this.list_items(source), ...this.dashboard_items(source)];
		}
		if (view === "query-report") {
			return [{ label: frappe.query_report.page_title }];
		}
		return [];
	},

	tree_items(source) {
		const doctype = source.doctype;
		const tree_title = frappe.treeview_settings?.[doctype]?.title || doctype;
		return [{ label: __(tree_title), href: `/desk/${frappe.router.slug(doctype)}` }];
	},

	list_items(source) {
		const doctype = source.doctype;
		const doctype_meta = frappe.get_meta(doctype);
		// no user listview for non-system managers and single doctypes
		if (
			(doctype === "User" && !frappe.user.has_role("System Manager")) ||
			doctype_meta?.issingle
		) {
			return [];
		}

		const doctype_route = frappe.router.slug(doctype);
		let route = doctype_route;
		if (doctype_meta?.is_tree) {
			const view = frappe.model.user_settings[doctype]?.last_view || "Tree";
			route = `${doctype_route}/view/${view}`;
		}
		const reset = source.layout_name ? "?reset_filters=1" : "";
		return [{ label: __(doctype), href: `/desk/${route}${reset}` }];
	},

	/** The DocType Layout crumb on a list, which is not a link. */
	layout_items(source) {
		if (!source.layout_name) return [];
		const layout_info = (frappe.boot.doctype_layouts || []).find(
			(l) => l.name === source.layout_name
		);
		return [{ label: __(layout_info?.title || source.layout_name) }];
	},

	form_items(source, view) {
		const doctype = source.doctype;
		const docname = frappe.get_route().slice(2).join("/");
		const doc = frappe.get_doc(doctype, docname);
		const form_route = `/desk/${frappe.router.slug(doctype)}/${encodeURIComponent(docname)}`;

		let docname_title;
		if (docname.startsWith("new-" + doctype.toLowerCase().replace(/ /g, "-"))) {
			docname_title = __("New {0}", [__(doctype)]);
		} else if (doc) {
			const title = frappe.model.get_doc_title(doc);
			docname_title = __(title) || __(doc.name);
			if (frappe.utils.is_html(docname_title)) {
				docname_title = strip_html(docname_title);
			}
		} else {
			docname_title = docname;
		}

		const items = [];
		if (source.layout_name) {
			const layout_info = (frappe.boot.doctype_layouts || []).find(
				(l) => l.name === source.layout_name
			);
			const filter_params = frappe.utils.parse_layout_condition_to_filters(
				layout_info?.condition
			);
			filter_params._layout = source.layout_name;
			const query = new URLSearchParams(filter_params).toString();
			items.push({
				label: __(layout_info?.title || source.layout_name),
				href: `/desk/${frappe.router.slug(doctype)}${query ? "?" + query : ""}`,
			});
		}

		// the form itself is the page, so it carries no link; the print view is a page past the
		// form, so there the docname stays a way back to it
		items.push(
			view === "form" ? { label: docname_title } : { label: docname_title, href: form_route }
		);
		return items;
	},

	dashboard_items(source) {
		// The page names the document it drew. The route segment is only a
		// fallback, because it carries whatever casing the link used. The label is
		// what the reader sees. An island may title a document differently from
		// its name, and the route must still reach the document.
		const docname = source.docname || frappe.get_route()[1];
		return [
			{
				label: __(source.label || docname),
				href: `/desk/${frappe.router.slug(source.doctype)}/${docname}`,
			},
		];
	},
};

// The legacy registry, keyed by route string. Nothing in this app reads or writes it. Writing an
// entry for the route on screen hands it to that page, so the old `all[route] = {...}` followed by
// `update()` still draws; a plain object could not be noticed.
const registry = {};

frappe.breadcrumbs.all = new Proxy(registry, {
	set(target, key, value) {
		target[key] = value;
		if (key === frappe.get_route_str()) {
			const page = frappe.get_current_page();
			if (page) page.legacy_breadcrumbs = value;
		}
		return true;
	},
});

// `$breadcrumbs` was the node callers appended markup to. It answers with the live list of the
// page on screen, which `render_breadcrumbs()` refills rather than replaces, so a held reference
// stays good. Whatever is appended here survives until the next paint, exactly as it did when
// `update()` wiped it.
Object.defineProperty(frappe.breadcrumbs, "$breadcrumbs", {
	get() {
		deprecated("$breadcrumbs", "`page.set_breadcrumbs(items)`.");
		return frappe.get_current_page()?.$breadcrumbs || $("<ol>");
	},
});

// Append to what is on screen. Reading `page.breadcrumbs` directly would drop the trail an
// earlier `add()` left, because that one is held as an unresolved payload.
function append_items(items) {
	const page = frappe.get_current_page();
	if (!page) return;
	page.set_breadcrumbs([...page.get_breadcrumbs(), ...items]);
}

const warned = new Set();

function deprecated(name, advice) {
	if (warned.has(name)) return;
	warned.add(name);
	console.warn(
		`\`frappe.breadcrumbs.${name}\` is deprecated. It is marked for removal in v17. ${advice}`
	);
}
