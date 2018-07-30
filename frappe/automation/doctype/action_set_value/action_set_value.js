// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Action Set Value', {
	refresh: function(frm) {
		frm.trigger('document_type');
	},
	document_type: function(frm) {
		frm.setup_fieldname_select('fieldname', frm.doc.document_type);
	}
});
