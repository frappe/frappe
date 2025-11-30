// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Desktop Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Visit Desktop"), () => frappe.set_route("desktop"));
	},
});
