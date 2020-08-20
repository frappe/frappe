// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Twilio Settings', {
	refresh: function(frm) {
		frm.dashboard.set_headline(__("For more information, {0}.", [`<a href='https://docs.erpnext.com/docs/user/manual/en/setting-up/notifications'>${__('Click here')}</a>`]));
	}
});
