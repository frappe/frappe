// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Desktop Item", {
	module(frm) {
		if (frm.doc.module) {
			frm.set_value("label", frm.doc.module);
		}
	},
});
