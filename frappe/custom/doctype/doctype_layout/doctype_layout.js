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
				if ((frm.doc.fields).length == 0 || (frm.doc.fields).length == 1) {
					if ((frm.doc.fields).length == 1) {
						frm.get_field("fields").grid.grid_rows[0].remove();
					}

					let field_names = [];

					for (let f of frappe.get_doc('DocType', frm.doc.document_type).fields) {
						frm.add_child('fields', { label: f.label });
						field_names.push(f.fieldname)
					}
					frm.fields_dict['fields'].grid.update_docfield_property('fieldname', 'options', field_names);
					frm.refresh_field('fields');
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
