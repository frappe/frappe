// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Energy Point Rule', {
	validate(frm) {
		frm.set_df_property('user_field', 'reqd', !frm.doc.for_assigned_users);
		frm.set_df_property('condition', 'reqd', frm.doc.for_doc_event==='Custom');
	},
	refresh(frm) {
		frm.events.set_field_options(frm);
	},
	for_doc_event(frm) {
		if (frm.doc.for_assigned_users) {
			frm.set_value('for_assigned_users', !frm.doc.for_doc_event==='New');
		}
	},
	reference_doctype(frm) {
		frm.events.set_field_options(frm);
	},
	set_field_options(frm) {
		// sets options for field_to_check, user_field and multiplier fields
		// based on reference doctype
		const reference_doctype = frm.doc.reference_doctype;
		if (!reference_doctype) return;

		frappe.model.with_doctype(reference_doctype, () => {
			const map_for_options = df => ({ label: df.label, value: df.fieldname });
			const fields = frappe.meta.get_docfields(frm.doc.reference_doctype)
				.filter(frappe.model.is_value_type);

			const fields_to_check = fields.map(map_for_options);

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

			frm.set_df_property('field_to_check', 'options', fields_to_check);
			frm.set_df_property('user_field', 'options', user_fields);
			frm.set_df_property('multiplier_field', 'options', multiplier_fields);
		});
	}
});
