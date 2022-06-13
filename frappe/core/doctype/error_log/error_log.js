// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Error Log", {
	refresh: function(frm) {
		if (frm.doc.reference_doctype && frm.doc.reference_name) {
			frm.add_custom_button(__("Show Errors for This Document"), function() {
				frappe.set_route("List", "Error Log", {
					reference_doctype: frm.doc.reference_doctype,
					reference_name: frm.doc.reference_name,
				});
			});
		}
	},
});
