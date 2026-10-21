// Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Studio Component", {
	refresh(frm) {
		if (frm.doc.is_standard && !frappe.boot.developer_mode) frm.disable_form();
	},
});
