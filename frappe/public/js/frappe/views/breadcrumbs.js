// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// The trail names the entity, never the shell it lives in: the dock names the app and the module
// sidebar names the module and highlights the entity within it, so a workspace crumb would
// repeat what the shell already says. This file therefore does not resolve an entity to a module
// or a workspace; that is `shell_for_route`'s job, and its answer is a shell. See
// ui/sidebar/sidebar.js.
//
// The trail is page-scoped state. Each `frappe.ui.Page` holds its own items and paints them into
// its own page head, so a view can only ever change the trail of the page it was handed. There is
// no ownership check anywhere here, because there is nothing to guard: a page that is not on
// screen paints into markup nobody is looking at.
//
// What is left in this file is the compatibility layer for `frappe.breadcrumbs.add()`, which apps
// outside this one still call. The views themselves use `page.set_breadcrumbs()`.
frappe.breadcrumbs = {
	/**
	 * The page an `add()` call means. Callers key off the route, the way this module always has,
	 * because a view often calls `add()` while its page is still being built and before the
	 * container has switched to it. The container's page is the fallback for a caller that has no
	 * page of its own registered under the route.
	 *
	 * @returns {frappe.ui.Page|null}
	 */
	current_page() {
		return frappe.ui.pages?.[frappe.get_route_str()] || frappe.container?.page?.page || null;
	},

	/**
	 * Legacy setter. `module` is kept in the signature for callers outside this app; nothing
	 * reads it.
	 *
	 * @param {string|Object} module Module name, or the whole options object
	 * @param {string} [doctype]
	 * @param {string} [type] "Custom" for a `{label, route}` crumb
	 */
	add(module, doctype, type) {
		const source =
			typeof module === "object" ? module : { module: module, doctype: doctype, type: type };

		const page = this.current_page();
		if (!page) return;

		page.set_legacy_breadcrumbs(source);
	},

	/** Repaint the current page's trail. */
	update() {
		this.current_page()?.render_breadcrumbs();
	},

	/**
	 * Resolve a legacy `add()` payload into espresso breadcrumb items, reading the route and the
	 * loaded doc the way `update()` always has. Everything below goes away as each view moves to
	 * `page.set_breadcrumbs()`.
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
			const view = frappe.model.user_settings[doctype].last_view || "Tree";
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
		} else {
			const title = frappe.model.get_doc_title(doc);
			docname_title = __(title) || __(doc.name);
			if (frappe.utils.is_html(docname_title)) {
				docname_title = strip_html(docname_title);
			}
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
