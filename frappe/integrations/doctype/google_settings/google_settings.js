// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Settings', {
	refresh: function(frm) {
		frm.dashboard.set_headline(__("For more information, <a href='https://erpnext.com/docs/user/manual/en/erpnext_integration/google_settings'>Click here</a>."));
	}
});