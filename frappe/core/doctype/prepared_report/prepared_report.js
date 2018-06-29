// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Prepared Report', {
	refresh: function(frm) {
		frm.add_custom_button(__("Show Report"), function() {
			frappe.set_route(
				"query-report",
				frm.doc.report_name,
				frappe.utils.make_query_string({
					prepared_report_name: frm.doc.name
				})
			);
		});
	}
});
