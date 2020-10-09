// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Assignment Rule', {
	onload: (frm) => {
		frm.trigger('set_due_date_field_options');
	},
	refresh: function(frm) {
		// refresh description
		frm.events.rule(frm);
	},
	rule: function(frm) {
		if (frm.doc.rule === 'Round Robin') {
			frm.get_field('rule').set_description(__('Assign one by one, in sequence'));
		} else {
			frm.get_field('rule').set_description(__('Assign to the one who has the least assignments'));
		}
	},
	document_type: (frm) => {
		frm.trigger('set_due_date_field_options');
	},
	set_due_date_field_options: (frm) => {
		let doctype = frm.doc.document_type;
		let datetime_fields = [];
		if (doctype) {
			frappe.model.with_doctype(doctype, () => {
				frappe.get_meta(doctype).fields.map((df) => {
					if (['Date', 'Datetime'].includes(df.fieldtype)) {
						datetime_fields.push({ label: df.label, value: df.fieldname });
					}
				});
				if (datetime_fields) {
					frm.set_df_property('due_date_based_on', 'options', datetime_fields);
				}
				frm.set_df_property('due_date_based_on', 'hidden', !datetime_fields.length);
			});
		}
	}
});
