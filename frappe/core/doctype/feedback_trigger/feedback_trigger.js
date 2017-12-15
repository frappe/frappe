// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Feedback Trigger', {
	onload: function(frm) {
		frm.set_query("document_type", function() {
			return {
				"filters": {
					"istable": 0
				}
			}
		})
	},

	refresh: function(frm) {
		frm.events.setup_field_options(frm);
	},

	document_type: function(frm) {
		frm.set_value('email_field', '');
		frm.set_value('email_fieldname');

		frm.events.setup_field_options(frm);
	},

	email_field: function(frm) {
		frm.set_value('email_fieldname', frm.fieldname_mapper[frm.doc.email_field]);
	},

	setup_field_options: function(frm) {
		frm.fieldname_mapper = {};
		frm.options = [];

		if(!frm.doc.document_type)
			return

		frappe.model.with_doctype(frm.doc.document_type, function() {
			var fields = frappe.get_doc("DocType", frm.doc.document_type).fields;
			$.each(fields, function(idx, field) {
				if(!in_list(frappe.model.no_value_type, field.fieldtype) && field.options == "Email") {
					frm.options.push(field.label);
					frm.fieldname_mapper[field.label] = field.fieldname;
				}
			})

			frm.set_df_property("email_field", "options", [""].concat(frm.options));
			frm.refresh_fields();
		});
	}
});
