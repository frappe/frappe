// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Log Settings', {
	refresh: function(frm) {
		frm.fields_dict['log_settings'].grid.get_field('ref_doctype').get_query = function() {
			return {
				query: 'frappe.core.doctype.log_settings.log_settings.get_log_doctypes'
			};
		};
	}
});