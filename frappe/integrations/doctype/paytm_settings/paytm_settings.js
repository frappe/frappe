// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Paytm Settings', {
	refresh: function(frm) {
		frm.dashboard.set_headline(__("For more information, {0}.", [`<a href='https://erpnext.com/docs/user/manual/en/erpnext_integration/paytm-integration'>${__('Click here')}</a>`]));
	}
});
