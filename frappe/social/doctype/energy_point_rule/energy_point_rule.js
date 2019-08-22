// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Energy Point Rule', {
	refresh: function(frm) {
		frm.events.set_user_and_multiplier_field_options(frm);
	},
	reference_doctype(frm) {
		frm.events.set_user_and_multiplier_field_options(frm);
	},
	set_user_and_multiplier_field_options(frm) {
		const reference_doctype = frm.doc.reference_doctype;
		if (!reference_doctype) return;

		frappe.model.with_doctype(reference_doctype, () => {
			const map_for_options = df => ({ label: df.label, value: df.fieldname });
			const fields = frappe.meta.get_docfields(frm.doc.reference_doctype);
			const user_fields = fields.filter(df => (df.fieldtype === 'Link' && df.options === 'User')
				|| df.fieldtype === 'Data')
				.map(map_for_options)
				.concat([
					{ label: __('Owner'), value: 'owner' },
					{ label: __('Modified By'), value: 'modified_by' }
				]);

			const multiplier_fields = fields.filter(df => ['Int', 'Float'].includes(df.fieldtype))
				.map(map_for_options);

			// blank option for the ability to unset the multiplier field
			multiplier_fields.unshift(null);

			frm.set_df_property('user_field', 'options', user_fields);
			frm.set_df_property('multiplier_field', 'options', multiplier_fields);
		});
	}
});
