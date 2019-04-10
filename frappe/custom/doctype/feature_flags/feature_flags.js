// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Feature Flags', {
	refresh: function(frm) {
		frm.set_intro(__('Enable experimental features. These features may be removed before they end up in the core.'))
	}
});
