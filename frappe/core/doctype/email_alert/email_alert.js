frappe.email_alert = {
	setup_fieldname_select: function(frm) {
		// get the doctype to update fields
		frappe.model.with_doctype(frm.doc.document_type, function() {

			frm._doctype_fields = $.map(frappe.get_doc("DocType", frm.doc.document_type).fields,
				function(d) { return in_list(frappe.model.no_value_type, d.fieldtype) ?
					null : d.fieldname; });

			var options = "\n" + frm._doctype_fields.join("\n");

			frm.set_df_property("value_changed", "options", options);

			frappe.meta.get_docfield("Email Alert Recipient", "email_by_document_field",
				frm.doc.name).options = options;

		});
	}
}

frappe.ui.form.on("Email Alert", "refresh", function(frm) {
	frappe.email_alert.setup_fieldname_select(frm)
});

frappe.ui.form.on("Email Alert", "document_type", function(frm) {
	frappe.email_alert.setup_fieldname_select(frm)
});
