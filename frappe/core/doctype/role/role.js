// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on('Role', {
		onload: function(frm) {
		frm.set_query("auth_field", "authorization", function(doc, cdt,cdn) {
			return {
				query: "frappe.core.doctype.role.role.get_auth_field",
				filters: {
					parent: locals[cdt][cdn].authorization_object
				},
			}
		});
	},

	refresh: function(frm) {
		frm.add_custom_button("Role Permissions Manager", function() {
			frappe.route_options = {"role": frm.doc.name};
			frappe.set_route("permission-manager");
		});
		frm.add_custom_button("Show Users", function() {
			frappe.route_options = {"role": frm.doc.name};
			frappe.set_route("List", "User", "Report");
		});
	}
});
