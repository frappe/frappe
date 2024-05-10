// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Module Sidebar", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on("Module Sidebar Item", {
	link_to(_, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (row.link_to) {
			frappe.model.set_value(cdt, cdn, "label", row.link_to);
		}
	},
});

frappe.ui.form.on("Module Sidebar Workspace", {
	workspace(_, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (row.workspace) {
			frappe.model.set_value(cdt, cdn, "label", row.workspace);
		}
	},
});
