// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Access Log', {
	refresh: function (frm) {
		if (frm.doc.hasOwnProperty('report_name') && frm.doc.report_name != 'Backup') {
			frm.set_df_property('show_report', 'hidden', 0);
		}
		if (frappe.db.exists(frm.doc.export_from, frm.doc.reference_document)) {
			frm.set_df_property('show_document', 'hidden', 0);
		}
	},

	show_document: function (frm) {
		frappe.set_route('Form', frm.doc.export_from, frm.doc.reference_document);
	},

	show_report: function (frm) {
		if (frm.doc.report_name.includes('/')) {
			frappe.set_route(frm.doc.report_name);
		} else {
			try {
				frappe.set_route('query-report', frm.doc.report_name, frm.doc._filters ? JSON.parse(frm.doc._filters) : '');
			} catch (err) {
				frappe.throw(__(err + ' has occurred'));
			}
		}
	}
});
