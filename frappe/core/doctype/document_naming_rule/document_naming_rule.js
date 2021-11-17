// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Document Naming Rule', {
	refresh: function(frm) {
		frm.trigger('document_type');
		if (!frm.doc.__islocal) frm.trigger("add_update_counter_button");
	},
	document_type: (frm) => {
		// update the select field options with fieldnames
		if (frm.doc.document_type) {
			frappe.model.with_doctype(frm.doc.document_type, () => {
				let fieldnames = frappe.get_meta(frm.doc.document_type).fields
					.filter((d) => {
						return frappe.model.no_value_type.indexOf(d.fieldtype) === -1;
					}).map((d) => {
						return {label: `${d.label} (${d.fieldname})`, value: d.fieldname};
					});
				frm.fields_dict.conditions.grid.update_docfield_property(
					'field', 'options', fieldnames
				);
			});
		}
	},
	add_update_counter_button: (frm) => {
		frm.add_custom_button(__('Update Counter'), function() {

			const fields = [{
				fieldtype: 'Data',
				fieldname: 'new_counter',
				label: __('New Counter'),
				default: frm.doc.counter,
				reqd: 1,
				description: __('Warning: Updating counter may lead to document name conflicts if not done properly')
			}];

			let primary_action_label = __('Save');

			let primary_action = (fields) => {
				frappe.call({
					method: 'frappe.core.doctype.document_naming_rule.document_naming_rule.update_current',
					args: {
						name: frm.doc.name,
						new_counter: fields.new_counter
					},
					callback: function() {
						frm.set_value("counter", fields.new_counter);
						dialog.hide();
					}
				});
			};

			const dialog = new frappe.ui.Dialog({
				title: __('Update Counter Value for Prefix: {0}', [frm.doc.prefix]),
				fields,
				primary_action_label,
				primary_action
			});

			dialog.show();

		});
	}
});
