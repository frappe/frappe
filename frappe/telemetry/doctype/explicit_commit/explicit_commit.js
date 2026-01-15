// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Explicit Commit", {
	refresh(frm) {
		frm.page.btn_primary.hide();
	},
});
