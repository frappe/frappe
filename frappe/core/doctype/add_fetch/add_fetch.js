// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Add Fetch', {
	onload: function(frm) {
		frm.trigger("for_doctype");
		frm.trigger("from_doctype");
	},
	for_doctype: function(frm) {
		const { for_doctype } = frm.doc;
		if (!for_doctype) return;

		frappe.model.with_doctype(for_doctype, () => {
			const meta = frappe.get_meta(for_doctype);

			const fieldnames = meta.fields.filter(
				df => !frappe.model.no_value_type.includes(df.fieldtype)
			).map(df => df.fieldname);

			frm.set_df_property('for_fieldname', 'options', fieldnames);
			frm.refresh();
		});
	},
	from_doctype: function(frm) {
		const { from_doctype } = frm.doc;
		if (!from_doctype) return;

		frappe.model.with_doctype(from_doctype, () => {
			const meta = frappe.get_meta(from_doctype);

			const fieldnames = meta.fields.filter(
				df => !frappe.model.no_value_type.includes(df.fieldtype)
			).map(df => df.fieldname);

			frm.set_df_property('from_fieldname', 'options', fieldnames);
			frm.refresh();
		});
	}
});
