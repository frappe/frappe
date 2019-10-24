// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('List View Settings', {
	refresh: function(frm) {
		frm.add_custom_button('Get List View Columns', function () {
			frappe.call({
				method: "frappe.desk.doctype.list_view_settings.list_view_settings.get_listview_columns",
				args: {
					doctype: frm.doc.name
				},
				callback: function (r) {
					if (r && r.message) {
						for (let i in r.message) {
							frm.add_child("column_order", r.message[i]);
						}
						frm.refresh();
					}
				}
			});
		});
	}
});
