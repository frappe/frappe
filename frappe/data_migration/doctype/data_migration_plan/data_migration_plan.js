// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Migration Plan', {
	refresh: function(frm) {
		frm.add_custom_button(__('Migrate'), () => {
			frappe.call({
				method: 'frappe.data_migration.doctype.data_migration_plan.data_migration_plan.migrate',
				args: {plan: frm.doc.name}
			});
		});
	}
});
