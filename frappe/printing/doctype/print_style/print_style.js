// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Print Style', {
	refresh: function(frm) {
		/* update in local */
		if (!frm.is_new() && !locals[':Print Style'][frm.doc.name]) {
			locals[':Print Style'][frm.doc.name] = frm.doc;
		}

		frm.add_custom_button(__('Print Settings'), () => {
			frappe.set_route('Form', 'Print Settings');
		})
	}
});
