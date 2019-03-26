// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('GSuite Templates', {
	refresh: function(frm) {
		if (frm.is_new()) {
			// if doc is new, get all options immediately
			set_available_docs(frm);
			set_available_folders(frm);
		}
	},
	template_id: function(frm) {
		if (!frm.is_new()) {
			// if doc is NOT new, get options when selecting field
			set_available_docs(frm);
		}
	},
	destination_id: function(frm) {
		if (!frm.is_new()) {
			// if doc is NOT new, get options when selecting field
			set_available_folders(frm);
		}
	}
});

const set_available_docs = (frm) => {
	frappe.call({
		method: 'frappe.integrations.doctype.gsuite_templates.gsuite_templates.get_gdrive_docs',
		callback: function(res) {
			// set available docs as options
			set_options(frm, 'template_id', res);
		}
	});
};

const set_available_folders = (frm) => {
	frappe.call({
		method: 'frappe.integrations.doctype.gsuite_templates.gsuite_templates.get_gdrive_folders',
		callback: function(res) {
			// set available folders as options
			set_options(frm, 'destination_id', res);
		}
	});
};

const set_options = (frm, field, data) => {
	var options = [];
	(data.message || []).forEach(function(row){ 
		options.push({'value': row.id, 'label': row.name});
	});
	frm.set_df_property(field, 'options', options);
};
