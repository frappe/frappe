// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on('Role', {
	refresh: function(frm) {
		frm.add_custom_button("Role Permissions Manager", function() {
			frappe.route_options = {"role": frm.doc.name};
			frappe.set_route("permission-manager");
		});
		frm.add_custom_button("Show Users", function() {
			frappe.route_options = {"role": frm.doc.name};
			frappe.set_route("Report", "User");
		});
	}
});
