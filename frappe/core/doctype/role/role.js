// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

cur_frm.cscript.refresh = function(doc) {
	cur_frm.permission_manager = cur_frm.add_custom_button("Role Permissions Manager", function() {
		frappe.route_options = {"role": doc.name};
		frappe.set_route("permission-manager");
	});
	cur_frm.set_intro('<a onclick="cur_frm.permission_manager.click()">'+__('Edit Permissions') + '</a>');
}
