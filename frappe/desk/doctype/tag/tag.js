// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tag", {
	refresh(frm) {
		frappe.xcall("frappe.apps.get_apps").then((apps) => {
			frm.fields_dict.apps.grid.update_docfield_property(
				"app_name",
				"options",
				apps.map((app) => app.name)
			);
		});
	},
});
