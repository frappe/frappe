// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Document Type Mapping", {
	local_doctype: function (frm) {
		if (frm.doc.local_doctype) {
			frappe.model.clear_table(frm.doc, "field_mapping");
			let fields = frm.events.get_fields(frm);
			$.each(fields, function (i, data) {
				let row = frappe.model.add_child(
					frm.doc,
					"Document Type Field Mapping",
					"field_mapping"
				);
				row.local_fieldname = data;
			});
			refresh_field("field_mapping");
		}
	},

	get_fields: function (frm) {
		let filtered_fields = [];
		frappe.model.with_doctype(frm.doc.local_doctype, () => {
			frappe.get_meta(frm.doc.local_doctype).fields.map((field) => {
				if (
					field.fieldname !== "remote_docname" &&
					field.fieldname !== "remote_site_name" &&
					frappe.model.is_value_type(field) &&
					!field.hidden
				) {
					filtered_fields.push(field.fieldname);
				}
			});
		});
		return filtered_fields;
	},
});
