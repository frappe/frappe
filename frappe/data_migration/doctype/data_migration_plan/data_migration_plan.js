// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Data Migration Plan', {
	onload(frm) {
		frm.add_custom_button(__('Run'), () => frappe.new_doc('Data Migration Run', {
			data_migration_plan: frm.doc.name
		}));
	}
});
