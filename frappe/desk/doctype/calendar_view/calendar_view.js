// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Calendar View', {
	onload: function(frm) {
		frm.trigger('reference_doctype');
	},
	reference_doctype: function(frm) {
		const { reference_doctype } = frm.doc;
		if (!reference_doctype) return;

		frappe.model.with_doctype(reference_doctype, () => {
			const meta = frappe.get_meta(reference_doctype);

			const subject_options = meta.fields.filter(
				df => !frappe.model.no_value_type.includes(df.fieldtype)
			).map(df => df.fieldname);

			const date_options = meta.fields.filter(
				df => ['Date', 'Datetime'].includes(df.fieldtype)
			).map(df => df.fieldname)

			frm.set_df_property('subject_field', 'options', subject_options);
			frm.set_df_property('start_date_field', 'options', date_options);
			frm.set_df_property('end_date_field', 'options', date_options);
			frm.refresh();
		});
	}
});
