frappe.email_alert = {
	setup_fieldname_select: function(frm) {
		// get the doctype to update fields
		if(!frm.doc.document_type) {
			return;
		}

		frappe.model.with_doctype(frm.doc.document_type, function() {
			var get_select_options = function(df) {
				return {value: df.fieldname, label: df.fieldname + " (" + __(df.label) + ")"};
			}

			var fields = frappe.get_doc("DocType", frm.doc.document_type).fields;

			var options = $.map(fields,
				function(d) { return in_list(frappe.model.no_value_type, d.fieldtype) ?
					null : get_select_options(d); });

			// set value changed options
			frm.set_df_property("value_changed", "options", [""].concat(options));

			// set date changed options
			frm.set_df_property("date_changed", "options", $.map(fields,
				function(d) { return (d.fieldtype=="Date" || d.fieldtype=="Datetime") ?
					get_select_options(d) : null; }));

			// set email recipient options
			frappe.meta.get_docfield("Email Alert Recipient", "email_by_document_field",
				frm.doc.name).options = ["owner"].concat(options);

		});
	}
}

frappe.ui.form.on("Email Alert", {
	refresh: function(frm) {
		frappe.email_alert.setup_fieldname_select(frm);
	},
	document_type: function(frm) {
		frappe.email_alert.setup_fieldname_select(frm);
	},
	view_properties: function(frm) {
		frappe.route_options = {doc_type:frm.doc.document_type};
		frappe.set_route("Form", "Customize Form");
	}
});
