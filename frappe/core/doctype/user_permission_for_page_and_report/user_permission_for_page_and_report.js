// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('User Permission for Page and Report', {
	refresh: function(frm) {
		frm.disable_save();
		frm.role_area.hide();
	},
	
	onload: function(frm) {
		if(!frm.roles_editor) {
			frm.role_area = $('<div style="min-height: 300px">')
				.appendTo(frm.fields_dict.roles_html.wrapper);
			frm.roles_editor = new frappe.RoleEditor(frm.role_area);
		}
	},
	
	page: function(frm) {
		frm.trigger("get_roles")
	},

	report: function(frm){
		frm.trigger("get_roles")
	},

	get_roles: function(frm) {
		frm.role_area.show();

		return frappe.call({
			method:"get_custom_roles",
			doc: frm.doc,
			callback: function(r) {
				refresh_field('roles')
				frm.roles_editor.show()
			}
		})
	},

	update: function(frm) {
		if(frm.roles_editor) {
			frm.roles_editor.set_roles_in_table()
		}

		return frappe.call({
			method:"set_custom_roles",
			doc: frm.doc,
			callback: function(r) {
				refresh_field('roles')
				frm.roles_editor.show()
				frappe.msgprint(__("Successfully Updated"))
				frm.reload_doc()
			}
		})
	}
});
