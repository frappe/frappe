// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('List View Settings', {
	refresh: function(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__('Go to {0} List', [frm.doc.name]), () => {
			frappe.set_route('List', frm.doc.name, 'List');
		});

		frm.add_custom_button('Get List View Columns', function () {
			frappe.call({
				method: "frappe.desk.doctype.list_view_settings.list_view_settings.get_listview_columns",
				args: {
					doctype: frm.doc.name
				},
				callback: function (r) {
					if (r && r.message) {
						render_fields(frm, r.message);
					}
				}
			});
		});

		if (frm.doc.column_order) {
			render_fields(frm, frm.doc.column_order);
		}
	}
});

function render_fields(frm, fields) {
	let columns_html = frm.get_field("column_order");
	columns_html.html(frappe.render_template("list_view_columns", {fields: fields}));
}