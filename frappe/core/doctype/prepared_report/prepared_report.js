// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Prepared Report', {
	refresh: function(frm) {
		frm.add_custom_button(__("Show Report"), function() {
			return frm.call({
				method: "frappe.core.doctype.prepared_report.prepared_report.get_report_attachment_data",
				args: {
					dn: frm.doc.name
				},
				callback: function(r) {
					if(r.message) {
						let data = r.message;
						frappe.flags.prepared_report = {
							data: data,
							name: frm.doc.name
						};

						frappe.set_route("query-report", frm.doc.report_name);
					}
				}
			});
		});

	}
});
