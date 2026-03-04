// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Workspace Sidebar", {
	refresh(frm) {
		if (frm.doc.standard && !frappe.boot.developer_mode) {
			frm.set_intro("This is a standard sidebar and cannot be edited");
			frm.set_read_only();
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__(`View Sidebar`), () => {
				if (frm.doc.items[0].link_type === "DocType") {
					frappe.set_route("List", frm.doc.items[0].link_to);
					return;
				} else if (frm.doc.items[0].link_type === "Workspace") {
					frappe.set_route("Workspaces", frm.doc.items[0].link_to);
					return;
				}
			});
		}
	},
	link_type: function (frm) {
		if (frm.doc.link_type == "URL") {
			frm.set_value("link_to", "");
		}
	},
});

frappe.ui.form.on("Workspace Sidebar Item", {
	form_render(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		let grid = frm.fields_dict.items.grid;
		let link_to = row.link_to;
		let row_obj = grid.get_grid_row(cdn);
		if (link_to && row.link_type === "DocType" && row_obj) {
			frappe.model.with_doctype(link_to, function () {
				let meta = frappe.get_meta(link_to);
				let field_obj = row_obj.get_field("navigate_to_tab");
				let tab_fieldnames = meta.fields
					.filter((field) => field.fieldtype === "Tab Break")
					.map((field) => field.fieldname);
				field_obj.set_data(tab_fieldnames);
				row_obj.refresh();
			});
		}
	},
});

frappe.ui.form.on("Workspace Sidebar Item", {
	form_render(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		let grid = frm.fields_dict.items.grid;
		let row_obj = grid.get_grid_row(cdn);
		let link_to = row.link_to;
		if (!row_obj) return;
		grid.update_docfield_property("filters", "hidden", 1);
		const field = row_obj.get_field("filter_area");
		if (!field) return;
		let filter_group = new frappe.ui.FilterGroup({
			parent: $(field.wrapper),
			doctype: link_to,
			on_change: () => {
				frm.dirty();
				let fieldname = "filters";
				let value = JSON.stringify(filter_group.get_filters());
				frappe.model.set_value(cdt, cdn, fieldname, value);
			},
		});
		$(field.wrapper).find(".filter-area").css("margin-bottom", "10px");
		$(field.wrapper)
			.find(".filter-area")
			.prepend("<label class='control-label'>Filters</label>");

		if (row.filters) {
			filter_group.add_filters_to_filter_group(JSON.parse(row.filters));
		}
	},
});
