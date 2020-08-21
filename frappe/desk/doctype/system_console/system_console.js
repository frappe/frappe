// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('System Console', {
	refresh: function(frm) {
		frm.disable_save();
		frm.page.set_primary_action(__("Execute"), () => {
			frm.execute_action('Execute');
		});
	}
});
