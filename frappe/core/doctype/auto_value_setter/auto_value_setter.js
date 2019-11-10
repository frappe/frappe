// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Auto Value Setter', {
	setup: function(frm) {
		frm.set_query('document_type', function () {
			return {
				"filters": {
					"issingle": 0
				}
			};
		});
	},

	refresh: function(frm) {
		frm.events.setup_fieldname_select(frm);
	},

	document_type: function(frm) {
		frm.events.setup_fieldname_select(frm);
	},

	setup_fieldname_select: function(frm) {
		// get the doctype to update fields
		if (!frm.doc.document_type) {
			return;
		}

		frappe.model.with_doctype(frm.doc.document_type, function() {
			let get_select_options = function(df) {
				return {value: df.fieldname, label: df.fieldname + " (" + __(df.label) + ")"};
			};

			let fields = frappe.get_doc("DocType", frm.doc.document_type).fields;
			let options = fields.map(d => in_list(frappe.model.no_value_type, d.fieldtype) ? null : get_select_options(d));
			options = options.filter(d => d);

			// set fieldname options
			frm.set_df_property("field_name", "options", [""].concat(options));

			frm.refresh_field('field_name');
		});
	}
});
