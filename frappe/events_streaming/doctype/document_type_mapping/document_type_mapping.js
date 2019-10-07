// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Document Type Mapping', {
	refresh: function(frm) {
		//set fieldname select
		if (frm.doc.local_doctype) {
			frappe.model.with_doctype(frm.doc.local_doctype, () => {
				//get doctype fields
				let fields = frm.events.get_fields(frm);
				frappe.meta.get_docfield('Document Type Field Mapping', 'local_fieldname', frm.doc.name).options = [''].concat(fields);
			});
		}
	},

	local_doctype: function(frm) {
		frappe.model.with_doctype(frm.doc.local_doctype, () => {
			let fields = frm.events.get_fields(frm);
			frappe.model.clear_table(frm.doc, 'field_mapping');
			$.each(fields, function(i, data) {
				let row = frappe.model.add_child(frm.doc, 'Document Type Mapping', 'field_mapping');
				row.local_fieldname = data.value;
			});
			refresh_field('field_mapping');
		});
	},

	get_fields: function(frm) {
		let fields = $.map(frappe.get_doc('DocType', frm.doc.local_doctype).fields, (data) => {
			if (frappe.model.no_value_type.includes(data.fieldtype) && !(frappe.model.table_fields.includes(data.fieldtype))) {
				return null;
			} else if(data.fieldname == 'remote_docname' || data.fieldname == 'remote_site_name') {
				return null;
			} else {
				return { label: data.fieldname, value: data.fieldname };
			}
		});
		return fields
	}
});
