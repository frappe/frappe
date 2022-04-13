// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('DocType Layout', {
	refresh: function(frm) {
		frm.trigger('document_type');
		frm.events.set_button(frm);
	},

	document_type(frm) {
		frm.set_fields_as_options('fields', frm.doc.document_type, null, [], 'fieldname').then(() => {
			// child table empty? then show all fields as default
			if (frm.doc.document_type) {
				if (!(frm.doc.fields || []).length) {
					for (let f of frappe.get_doc('DocType', frm.doc.document_type).fields) {
						frm.add_child('fields', { fieldname: f.fieldname, label: f.label });
					}
				}
			}
		});
	},

	set_button(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Go to {0} List', [frm.doc.name]), () => {
				window.open(`/app/${frappe.router.slug(frm.doc.name)}`);
			});
		}
	}
});
