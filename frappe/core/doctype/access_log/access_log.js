// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Access Log', {
	refresh: function (frm) {
		frm.fields_dict.report_name.$input_wrapper.on("click", function () {
			if (frm.doc.report_name.includes('/')) {
				frappe.set_route(frm.doc.report_name);
			} else {
				try {
					frappe.set_route('query-report', frm.doc.report_name, frm.doc.filters ? JSON.parse(frm.doc.filters) : '');
				} catch (err) {
					frappe.throw(__(err + ' has occurred'));
				}
			}
		});
	}
});
