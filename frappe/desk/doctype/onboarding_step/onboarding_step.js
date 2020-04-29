// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Onboarding Step', {
	refresh: function(frm) {
		if (frm.doc.reference_document && frm.doc.action == "Update Settings") {
			setup_fields(frm);
		}
	},

	reference_document: function(frm) {
		if (frm.doc.reference_document && frm.doc.action == "Update Settings") {
			setup_fields(frm);
		}
	}
});

function setup_fields(frm) {
	if (frm.doc.reference_document && frm.doc.action == "Update Settings") {
		frappe.model.with_doctype(frm.doc.reference_document, () => {
			let fields = frappe.get_meta(frm.doc.reference_document).fields.filter(df => {
				return ["Data", "Check", "Int", "Link", "Select"].includes(df.fieldtype);
			}).map(df => {
				return {
						"label": `${__(df.label)} (${df.fieldname})`,
						"value": df.fieldname
					}
			});

			frm.set_df_property('field', 'options', fields)
		});
	}
}
