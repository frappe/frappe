// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('GSuite Templates', {
	refresh: function(frm) {
		if (frm.is_new()) {
			// if doc is new, get all options immediately
			frm.trigger('set_available_docs');
			frm.trigger('set_available_folders');
		}
	},
	set_available_docs: function(frm) {
		frappe.call({
			// get documents from Google Drive
			method: 'frappe.integrations.doctype.gsuite_templates.gsuite_templates.get_gdrive_docs',
			callback: function(res) {
				// set available documents as options
				set_gsuite_template_options(frm, 'template_id', res);
			}
		});
	},
	set_available_folders: function(frm) {
		frappe.call({
			// get folders from Google Drive
			method: 'frappe.integrations.doctype.gsuite_templates.gsuite_templates.get_gdrive_folders',
			callback: function(res) {
				// set available folders as options
				set_gsuite_template_options(frm, 'destination_id', res);
			}
		});
	},
});

const set_gsuite_template_options = function(frm, field, data) {
	var options = [];
	(data.message || []).forEach(function(row){ 
		options.push({'value': row.id, 'label': row.name});
	});
	frm.set_df_property(field, 'options', options);
};

