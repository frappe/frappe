// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.breadcrumbs = {
	all: {},

	preferred: {
		File: "",
		Dashboard: "Customization",
		"Dashboard Chart": "Customization",
		"Dashboard Chart Source": "Customization",
	},

	module_map: {
		Core: "Settings",
		Email: "Settings",
		Custom: "Settings",
		Workflow: "Settings",
		Printing: "Settings",
		Setup: "Settings",
		Automation: "Tools",
	},

	set_doctype_module(doctype, module) {
		localStorage["preferred_breadcrumbs:" + doctype] = module;
	},

	get_doctype_module(doctype) {
		return localStorage["preferred_breadcrumbs:" + doctype];
	},

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
			// workspace
			this.set_workspace_breadcrumb(breadcrumbs);

			// form / print
			let view = frappe.get_route()[0];
			view = view ? view.toLowerCase() : null;
			if (breadcrumbs.doctype && ["print", "form"].includes(view)) {
				this.set_list_breadcrumb(breadcrumbs);
				this.set_form_breadcrumb(breadcrumbs, view);
			} else if (breadcrumbs.doctype && view === "list") {
				this.set_list_breadcrumb(breadcrumbs);
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

	get last_route() {
		return frappe.route_history.slice(-2)[0];
	},

	set_workspace_breadcrumb(breadcrumbs) {
		// get preferred module for breadcrumbs, based on history and module

		if (!breadcrumbs.workspace) {
			this.set_workspace(breadcrumbs);
		}

		if (!breadcrumbs.workspace) {
			return;
		}

		if (
			breadcrumbs.module_info &&
			(breadcrumbs.module_info.blocked ||
				!frappe.visible_modules.includes(breadcrumbs.module_info.module))
		) {
			return;
		}
		if (frappe.app.sidebar.sidebar_title) {
			let icon = frappe.utils.get_desktop_icon_by_label(frappe.app.sidebar.sidebar_title);
			let url = frappe.utils.get_route_for_icon(icon);
			if (url) {
				this.append_breadcrumb_element(url, __(icon.label), "worksapce-breadcrumb");
			}
		}

		let worksapce_crumb = this.$breadcrumbs.find("li a.worksapce-breadcrumb");

		worksapce_crumb.parent().addClass("ellipsis");
	},

	set_workspace(breadcrumbs) {
		// try and get module from doctype or other settings
		// then get the workspace for that module

		this.setup_modules();
		var from_module = this.get_doctype_module(breadcrumbs.doctype);

		if (from_module) {
			breadcrumbs.module = from_module;
		} else if (this.preferred[breadcrumbs.doctype] !== undefined) {
			// get preferred module for breadcrumbs
			breadcrumbs.module = this.preferred[breadcrumbs.doctype];
		}

		// guess from last route
		if (this.last_route?.[0] == "Workspaces") {
			let last_workspace = this.last_route[1];

			if (
				breadcrumbs.module &&
				frappe.boot.module_wise_workspaces[breadcrumbs.module]?.includes(last_workspace)
			) {
				breadcrumbs.workspace = last_workspace;
			}
		} else {
			// choose from __workspaces
			const doctype_meta = frappe.get_meta(breadcrumbs.doctype);
			if (doctype_meta?.__workspaces?.length) {
				breadcrumbs.workspace = doctype_meta.__workspaces[0];
			}

			if (breadcrumbs.module) {
				if (this.module_map[breadcrumbs.module]) {
					breadcrumbs.module = this.module_map[breadcrumbs.module];
				}

				breadcrumbs.module_info = frappe.get_module(breadcrumbs.module);

				// set workspace
				if (
					breadcrumbs.module_info &&
					frappe.boot.module_wise_workspaces[breadcrumbs.module]
				) {
					breadcrumbs.workspace =
						frappe.boot.module_wise_workspaces[breadcrumbs.module][0];
				}
			}
		}
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
			const doctype_route = frappe.router.slug(frappe.router.doctype_layout || doctype);
			if (doctype_meta?.is_tree) {
				let view = frappe.model.user_settings[doctype].last_view || "Tree";
				route = `${doctype_route}/view/${view}`;
			} else {
				route = doctype_route;
			}
			this.append_breadcrumb_element(`/desk/${route}`, __(doctype), "title-text");
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
			docname_title = title || doc.name;
			if (frappe.utils.is_html(docname_title)) {
				docname_title = strip_html(docname_title);
			}
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
		const docname = frappe.get_route()[1];
		let dashboard_route = `/desk/${frappe.router.slug(doctype)}/${docname}`;
		$(`<li><a href="${dashboard_route}">${__(docname)}</a></li>`).appendTo(this.$breadcrumbs);
	},

	setup_modules() {
		if (!frappe.visible_modules) {
			frappe.visible_modules = $.map(frappe.boot.allowed_workspaces, (m) => {
				return m.module;
			});
		}
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
		this.append_breadcrumb_element("/desk", frappe.utils.icon("monitor"));
	},

	toggle(show) {
		if (show) {
			$("body").addClass("no-breadcrumbs");
		} else {
			$("body").removeClass("no-breadcrumbs");
		}
	},
};
