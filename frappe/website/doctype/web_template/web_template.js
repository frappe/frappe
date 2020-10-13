// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Web Template', {
	refresh(frm) {
		if (!frappe.boot.developer_mode && frm.doc.standard) {
			frm.disable_form();
		}

		frm.toggle_display('standard', frappe.boot.developer_mode);
	}
});
