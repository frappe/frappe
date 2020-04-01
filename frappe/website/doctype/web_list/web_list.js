// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Web List', {
	refresh: function(frm) {
		return frm.trigger('reference_doctype');
	},
	reference_doctype: function(frm) {
		// update Select fields in the child tables
		if (frm.doc.reference_doctype) {
			// fetch fields
			return frappe.model.with_doctype(frm.doc.reference_doctype, function() {
				// map fields with value
				var fields = $.map(frappe.get_doc("DocType", frm.doc.reference_doctype).fields, function(d) {
					if (frappe.model.no_value_type.indexOf(d.fieldtype) === -1) {
						return { label: d.label + ' (' + d.fieldtype + ')', value: d.fieldname };
					} else {
						return null;
					}
				});

				fields.unshift({label: __("Name"), value: "name"});

				// update the `options` property with the fields
				frappe.meta.get_docfield("Web List Filter", "fieldname", frm.doc.name).options = [""].concat(fields);
				frappe.meta.get_docfield("Web List Column", "fieldname", frm.doc.name).options = [""].concat(fields);
			});
		}
	}
});
