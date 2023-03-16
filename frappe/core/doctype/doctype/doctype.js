// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("DocType", {
	refresh: function (frm) {
		frm.set_query("role", "permissions", function (doc) {
			if (doc.custom && frappe.session.user != "Administrator") {
				return {
					query: "frappe.core.doctype.role.role.role_query",
					filters: [["Role", "name", "!=", "All"]],
				};
			}
		});

		if (frappe.session.user !== "Administrator" || !frappe.boot.developer_mode) {
			if (frm.is_new()) {
				frm.set_value("custom", 1);
			}
			frm.toggle_enable("custom", 0);
			frm.toggle_enable("is_virtual", 0);
			frm.toggle_enable("beta", 0);
		}

		!frm.is_new() &&
			frm.add_custom_button(__("Try new form builder", [__(frm.doc.name)]), () => {
				frappe.set_route("form-builder", frm.doc.name);
			});

		if (!frm.is_new() && !frm.doc.istable) {
			if (frm.doc.issingle) {
				frm.add_custom_button(__("Go to {0}", [__(frm.doc.name)]), () => {
					window.open(`/app/${frappe.router.slug(frm.doc.name)}`);
				});
			} else {
				frm.add_custom_button(__("Go to {0} List", [__(frm.doc.name)]), () => {
					window.open(`/app/${frappe.router.slug(frm.doc.name)}`);
				});
			}
		}

		const customize_form_link = "<a href='/app/customize-form'>Customize Form</a>";
		if (!frappe.boot.developer_mode && !frm.doc.custom) {
			// make the document read-only
			frm.set_read_only();
			frm.dashboard.clear_comment();
			frm.dashboard.add_comment(
				__("DocTypes can not be modified, please use {0} instead", [customize_form_link]),
				"blue",
				true
			);
		} else if (frappe.boot.developer_mode) {
			frm.dashboard.clear_comment();
			let msg = __(
				"This site is running in developer mode. Any change made here will be updated in code."
			);
			msg += "<br>";
			msg += __("If you just want to customize for your site, use {0} instead.", [
				customize_form_link,
			]);
			frm.dashboard.add_comment(msg, "yellow", true);
		}

		if (frm.is_new()) {
			frm.events.set_default_permission(frm);
			frm.set_value("default_view", "List");
		} else {
			frm.toggle_enable("engine", 0);
		}

		// set label for "In List View" for child tables
		frm.get_docfield("fields", "in_list_view").label = frm.doc.istable
			? __("In Grid View")
			: __("In List View");

		frm.cscript.autoname(frm);
		frm.cscript.set_naming_rule_description(frm);
		frm.trigger("setup_default_views");
	},

	istable: (frm) => {
		if (frm.doc.istable && frm.is_new()) {
			frm.set_value("default_view", null);
		} else if (!frm.doc.istable && !frm.is_new()) {
			frm.events.set_default_permission(frm);
		}
	},

	set_default_permission: (frm) => {
		if (!(frm.doc.permissions && frm.doc.permissions.length)) {
			frm.add_child("permissions", { role: "System Manager" });
		}
	},

	is_tree: (frm) => {
		frm.trigger("setup_default_views");
	},

	is_calendar_and_gantt: (frm) => {
		frm.trigger("setup_default_views");
	},

	setup_default_views: (frm) => {
		frappe.model.set_default_views_for_doctype(frm.doc.name, frm);
	},
});

frappe.ui.form.on("DocField", {
	form_render(frm, doctype, docname) {
		frm.trigger("setup_fetch_from_fields", doctype, docname);
	},

	fieldtype: function (frm) {
		frm.trigger("max_attachments");
	},

	fields_add: (frm) => {
		frm.trigger("setup_default_views");
	},
});

extend_cscript(cur_frm.cscript, new frappe.model.DocTypeController({ frm: cur_frm }));
