// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Document Naming Rule', {
	refresh: function(frm) {
		frm.trigger('document_type');
	},
	document_type: (frm) => {
		// update the select field options with fieldnames
		if (frm.doc.document_type) {
			frappe.model.with_doctype(frm.doc.document_type, () => {
				let fieldnames = frappe.get_meta(frm.doc.document_type).fields
					.filter((d) => {
						return frappe.model.no_value_type.indexOf(d.fieldtype) === -1;
					}).map((d) => {
						return {label: `${d.label} (${d.fieldname})`, value: d.fieldname};
					});
				frm.fields_dict.conditions.grid.update_docfield_property(
					'field', 'options', fieldnames
				);
			});
		}
	}
});
