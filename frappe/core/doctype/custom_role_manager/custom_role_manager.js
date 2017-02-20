// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Custom Role Manager', {
	refresh: function(frm) {
		frm.disable_save();
	},
	
	onload: function(frm) {
		if(!frm.roles_editor) {
			var role_area = $('<div style="min-height: 300px">')
				.appendTo(frm.fields_dict.roles_html.wrapper);
			frm.roles_editor = new frappe.RoleEditor(role_area);
		}
	},
	
	page: function(frm) {
		frappe.call({
			method:"get_custom_roles",
			doc: frm.doc,
			callback: function(r) {
				refresh_field('has_roles')
				frm.roles_editor.show()
			}
		})
	}
});
