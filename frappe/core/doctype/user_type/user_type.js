// Copyright (c) 2021, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('User Type', {
	refresh: function(frm) {
		frm.toggle_display('is_standard', frappe.boot.developer_mode ? true : false);
		frm.set_df_property('is_standard', 'read_only', frappe.boot.developer_mode ? false : true);

		frm.set_query('document_type', 'user_doctypes', function() {
			return {
				filters: {
					istable: 0
				}
			};
		});
	}
});
