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
		frappe.app.sidebar.set_active_workspace_item();
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
				// pass
			} else if (breadcrumbs.doctype && view == "dashboard-view") {
				this.set_list_breadcrumb(breadcrumbs);
			}
		}

		if (
			breadcrumbs.workspace &&
			frappe.workspace_map[breadcrumbs.workspace]?.app &&
			frappe.workspace_map[breadcrumbs.workspace]?.app != frappe.current_app
		) {
			let app = frappe.workspace_map[breadcrumbs.workspace].app;
			frappe.app.sidebar.apps_switcher.set_current_app(app);
		}

		this.toggle(true);
	},

	set_custom_breadcrumbs(breadcrumbs) {
		this.append_breadcrumb_element(breadcrumbs.route, breadcrumbs.label);
	},

	append_breadcrumb_element(route, label) {
		const el = document.createElement("li");
		const a = document.createElement("a");
		a.href = route;
		a.innerText = label;
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

		this.append_breadcrumb_element(
			`/app/${frappe.router.slug(breadcrumbs.workspace)}`,
			__(breadcrumbs.workspace)
		);
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
			this.append_breadcrumb_element(`/app/${route}`, __(doctype));
		}
	},

	set_form_breadcrumb(breadcrumbs, view) {
		const doctype = breadcrumbs.doctype;
		let docname = frappe.get_route().slice(2).join("/");
		let doc = frappe.get_doc(doctype, docname);

		if (doc.__islocal) return; // new doc, no breadcrumb required

		let title = frappe.model.get_doc_title(doc);

		if (title == doc.name) return; // title and name are same, don't add breadcrumb

		let form_route = `/app/${frappe.router.slug(doctype)}/${encodeURIComponent(docname)}`;
		this.append_breadcrumb_element(form_route, doc.name);

		if (view === "form") {
			let last_crumb = this.$breadcrumbs.find("li").last();
			last_crumb.addClass("disabled");
			last_crumb.css("cursor", "copy");
			last_crumb.click((event) => {
				event.stopImmediatePropagation();
				frappe.utils.copy_to_clipboard(last_crumb.text());
			});
		}
	},

	set_dashboard_breadcrumb(breadcrumbs) {
		const doctype = breadcrumbs.doctype;
		const docname = frappe.get_route()[1];
		let dashboard_route = `/app/${frappe.router.slug(doctype)}/${docname}`;
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
		this.$breadcrumbs = $("#navbar-breadcrumbs").empty();
	},

	toggle(show) {
		if (show) {
			$("body").addClass("no-breadcrumbs");
		} else {
			$("body").removeClass("no-breadcrumbs");
		}
	},
};
