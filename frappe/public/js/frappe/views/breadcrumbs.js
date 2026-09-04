// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// The trail names the entity, never the shell it lives in: the dock names the app and the module
// sidebar names the module and highlights the entity within it, so a workspace crumb would
// repeat what the shell already says. This file therefore does not resolve an entity to a module
// or a workspace; that is resolve_initial_sidebar's job, and its answer is a module. See
// ui/sidebar/sidebar.js.
frappe.breadcrumbs = {
	all: {},

	// `module` is kept in the signature for callers outside this app; nothing reads it.
	add(module, doctype, type) {
		let obj;
		if (typeof module === "object") {
			obj = module;
		} else {
			obj = {
				module: module,
				doctype: doctype,
				type: type,
			};
		}
		this.all[frappe.breadcrumbs.current_page()] = obj;
		this.update();
	},

	current_page() {
		return frappe.get_route_str();
	},

	set_tree_breadcrumb(breadcrumbs) {
		const doctype = breadcrumbs.doctype;
		const tree_title = frappe.treeview_settings?.[doctype]?.title || doctype;

		this.append_breadcrumb_element(
			`/desk/${frappe.router.slug(doctype)}`,
			__(tree_title),
			"title-text"
		);

		let tree_crumb = this.$breadcrumbs.find("li a.title-text").last();
		tree_crumb.parent().addClass("ellipsis");
	},

	update() {
		var breadcrumbs = this.all[frappe.breadcrumbs.current_page()];

		this.clear();
		if (!breadcrumbs) return this.toggle(false);
		if (breadcrumbs.type === "Custom") {
			this.set_custom_breadcrumbs(breadcrumbs);
			if (breadcrumbs.menu_items && breadcrumbs.menu_items.length) {
				let breadcrumbs_container = $(".navbar-breadcrumbs");
				breadcrumbs_container.each((index, container) => {
					let last_element = $(container)
						.find("li")
						.get($(container).find("li").length - 1);
					$(last_element).find("a").attr("href", "");
					frappe.ui.create_menu({
						parent: $(last_element),
						menu_items: breadcrumbs.menu_items,
						size: "fit-content",
					});
				});
			}
		} else {
			// form / print
			let view = frappe.get_route()[0];
			view = view ? view.toLowerCase() : null;
			if (breadcrumbs.doctype && ["print", "form"].includes(view)) {
				this.set_list_breadcrumb(breadcrumbs);
				this.set_form_breadcrumb(breadcrumbs, view);
			} else if (breadcrumbs.doctype && view === "tree") {
				this.set_tree_breadcrumb(breadcrumbs);
			} else if (breadcrumbs.doctype && view === "list") {
				this.set_list_breadcrumb(breadcrumbs);
				if (breadcrumbs.layout_name) {
					const layout_info = (frappe.boot.doctype_layouts || []).find(
						(l) => l.name === breadcrumbs.layout_name
					);
					const display_title = layout_info?.title || breadcrumbs.layout_name;
					const $li = this.$breadcrumbs.find("li").last();
					$li.after(
						`<li class="disabled"><a>${frappe.utils.escape_html(
							__(display_title)
						)}</a></li>`
					);
				}
			} else if (breadcrumbs.doctype && view == "dashboard-view") {
				this.set_list_breadcrumb(breadcrumbs);
				this.set_dashboard_breadcrumb(breadcrumbs);
			} else if (view == "query-report") {
				breadcrumbs.label = frappe.query_report.page_title;
				this.append_breadcrumb_element("", breadcrumbs.label);
			}
		}

		this.toggle(true);
	},

	set_custom_breadcrumbs(breadcrumbs) {
		this.append_breadcrumb_element(breadcrumbs.route, breadcrumbs.label);
	},

	append_breadcrumb_element(route, label, css_classes) {
		const el = document.createElement("li");
		const a = document.createElement("a");
		if (route) {
			a.href = route;
		}
		if (css_classes) {
			a.classList.add(css_classes);
		}
		a.innerHTML = label;
		el.appendChild(a);
		this.$breadcrumbs.append(el);
	},

	set_list_breadcrumb(breadcrumbs) {
		const doctype = breadcrumbs.doctype;
		const doctype_meta = frappe.get_meta(doctype);
		if (
			(doctype === "User" && !frappe.user.has_role("System Manager")) ||
			doctype_meta?.issingle
		) {
			// no user listview for non-system managers and single doctypes
		} else {
			let route;
			const doctype_route = frappe.router.slug(doctype);
			if (doctype_meta?.is_tree) {
				let view = frappe.model.user_settings[doctype].last_view || "Tree";
				route = `${doctype_route}/view/${view}`;
			} else {
				route = doctype_route;
			}
			const reset = breadcrumbs.layout_name ? "?reset_filters=1" : "";
			this.append_breadcrumb_element(`/desk/${route}${reset}`, __(doctype), "title-text");
		}

		let list_crumb = this.$breadcrumbs.find("li a.title-text");
		list_crumb.parent().addClass("ellipsis");
	},

	set_form_breadcrumb(breadcrumbs, view) {
		const doctype = breadcrumbs.doctype;
		let docname = frappe.get_route().slice(2).join("/");
		let doc = frappe.get_doc(doctype, docname);
		let form_route = `/desk/${frappe.router.slug(doctype)}/${encodeURIComponent(docname)}`;

		let docname_title;
		let is_new_doc = false;
		if (docname.startsWith("new-" + doctype.toLowerCase().replace(/ /g, "-"))) {
			docname_title = __("New {0}", [__(doctype)]);
			is_new_doc = true;
		} else {
			let title = frappe.model.get_doc_title(doc);
			docname_title = __(title) || __(doc.name);
			if (frappe.utils.is_html(docname_title)) {
				docname_title = strip_html(docname_title);
			}
		}

		if (breadcrumbs.layout_name) {
			const layout_info = (frappe.boot.doctype_layouts || []).find(
				(l) => l.name === breadcrumbs.layout_name
			);
			const display_title = layout_info?.title || breadcrumbs.layout_name;
			const doctype_slug = frappe.router.slug(doctype);
			const filter_params = frappe.utils.parse_layout_condition_to_filters(
				layout_info?.condition
			);
			filter_params._layout = breadcrumbs.layout_name;
			const query = new URLSearchParams(filter_params).toString();
			const layout_route = `/desk/${doctype_slug}${query ? "?" + query : ""}`;
			this.append_breadcrumb_element(layout_route, __(display_title));
		}

		this.append_breadcrumb_element(form_route, docname_title, "title-text-form");

		if (view === "form") {
			let last_crumb = this.$breadcrumbs.find(".title-text-form").parent();
			last_crumb.addClass("disabled");
			if (frappe.is_mobile()) {
				last_crumb.addClass("ellipsis");
				last_crumb.find("a").addClass("ellipsis");
			}
		}
	},

	set_dashboard_breadcrumb(breadcrumbs) {
		const doctype = breadcrumbs.doctype;
		// The page names the document it drew. The route segment is only a
		// fallback: it carries whatever casing the link that reached here used.
		// The label is what the reader sees; an island may title a document
		// differently from its name, and the route must still reach the document.
		const docname = breadcrumbs.docname || frappe.get_route()[1];
		const label = breadcrumbs.label || docname;
		let dashboard_route = `/desk/${frappe.router.slug(doctype)}/${docname}`;
		$(
			`<li><a href="${frappe.utils.escape_html(dashboard_route)}">${frappe.utils.escape_html(
				__(label)
			)}</a></li>`
		).appendTo(this.$breadcrumbs);
	},

	rename(doctype, old_name, new_name) {
		var old_route_str = ["Form", doctype, old_name].join("/");
		var new_route_str = ["Form", doctype, new_name].join("/");
		this.all[new_route_str] = this.all[old_route_str];
		delete frappe.breadcrumbs.all[old_route_str];
		this.update();
	},

	clear() {
		this.$breadcrumbs = $(".navbar-breadcrumbs").empty();
	},

	toggle(show) {
		if (show) {
			$("body").addClass("no-breadcrumbs");
		} else {
			$("body").removeClass("no-breadcrumbs");
		}
	},

	/**
	 * Parse a layout condition string into URL query params for list filtering.
	 * Handles AND-joined `doc.field OP value` comparisons.
	 * Returns {} for conditions that contain || (OR) since those can't be expressed as simple filters.
	 */
};
