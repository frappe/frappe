// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Custom Role Manager', {
	refresh: function(frm) {
		frm.disable_save();
	},

	get_roles: function(frm) {
		frappe.call({
			method: "get_custom_roles",
			doc: frm.doc,
			callback: function(r) {
				refresh_field('roles')
			}
		})
	}
});
