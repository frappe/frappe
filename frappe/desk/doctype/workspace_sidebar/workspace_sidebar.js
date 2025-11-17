// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Workspace Sidebar", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__(`View Sidebar`), () => {
				if (frm.doc.items[0].link_type === "DocType") {
					frappe.set_route("List", frm.doc.items[0].link_to);
					return;
				} else if (frm.doc.items[0].link_type === "Workspace") {
					frappe.set_route("Workspaces", frm.doc.items[0].link_to);
					return;
				}
			});
		}
	},
});
