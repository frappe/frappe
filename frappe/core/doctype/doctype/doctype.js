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
			frm.dashboard.add_comment(
				__("DocTypes can not be modified, please use {0} instead", [customize_form_link]),
				"blue",
				true
			);
		} else if (frappe.boot.developer_mode) {
			let msg = __(
				"This site is running in developer mode. Any change made here will be updated in code."
			);
			msg += "<br>";
			msg += __("If you just want to customize for your site, use {0} instead.", [
				customize_form_link,
			]);
			frm.dashboard.add_comment(msg, "yellow");
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
		// Render two select fields for Fetch From instead of Small Text for better UX
		let field = frm.cur_grid.grid_form.fields_dict.fetch_from;
		$(field.input_area).hide();

		let $doctype_select = $(`<select class="form-control">`);
		let $field_select = $(`<select class="form-control">`);
		let $wrapper = $('<div class="fetch-from-select row"><div>');
		$wrapper.append($doctype_select, $field_select);
		field.$input_wrapper.append($wrapper);
		$doctype_select.wrap('<div class="col"></div>');
		$field_select.wrap('<div class="col"></div>');

		let row = frappe.get_doc(doctype, docname);
		let curr_value = { doctype: null, fieldname: null };
		if (row.fetch_from) {
			let [doctype, fieldname] = row.fetch_from.split(".");
			curr_value.doctype = doctype;
			curr_value.fieldname = fieldname;
		}

		let doctypes = frm.doc.fields
			.filter((df) => df.fieldtype == "Link")
			.filter((df) => df.options && df.fieldname != row.fieldname)
			.sort((a, b) => a.options.localeCompare(b.options))
			.map((df) => ({
				label: `${df.options} (${df.fieldname})`,
				value: df.fieldname,
			}));
		$doctype_select.add_options([
			{ label: __("Select DocType"), value: "", selected: true },
			...doctypes,
		]);

		$doctype_select.on("change", () => {
			row.fetch_from = "";
			frm.dirty();
			update_fieldname_options();
		});

		function update_fieldname_options() {
			$field_select.find("option").remove();

			let link_fieldname = $doctype_select.val();
			if (!link_fieldname) return;
			let link_field = frm.doc.fields.find((df) => df.fieldname === link_fieldname);
			let link_doctype = link_field.options;
			frappe.model.with_doctype(link_doctype, () => {
				let fields = frappe.meta
					.get_docfields(link_doctype, null, {
						fieldtype: ["not in", frappe.model.no_value_type],
					})
					.sort((a, b) => a.label.localeCompare(b.label))
					.map((df) => ({
						label: `${df.label} (${df.fieldtype})`,
						value: df.fieldname,
					}));
				$field_select.add_options([
					{
						label: __("Select Field"),
						value: "",
						selected: true,
						disabled: true,
					},
					...fields,
				]);

				if (curr_value.fieldname) {
					$field_select.val(curr_value.fieldname);
				}
			});
		}

		$field_select.on("change", () => {
			let fetch_from = `${$doctype_select.val()}.${$field_select.val()}`;
			row.fetch_from = fetch_from;
			frm.dirty();
		});

		if (curr_value.doctype) {
			$doctype_select.val(curr_value.doctype);
			update_fieldname_options();
		}
	},

	fieldtype: function (frm) {
		frm.trigger("max_attachments");
	},

	fields_add: (frm) => {
		frm.trigger("setup_default_views");
	},
});

extend_cscript(cur_frm.cscript, new frappe.model.DocTypeController({ frm: cur_frm }));
