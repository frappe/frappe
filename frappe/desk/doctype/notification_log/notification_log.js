// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Notification Log', {
	open_reference_document: function(frm) {
		let dt = frm.doc.document_type;
		let dn = frm.doc.document_name;
		frappe.set_route('Form', dt, dn);
	}
});
