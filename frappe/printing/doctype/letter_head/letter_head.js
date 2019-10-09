// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Letter Head', {
	refresh: function(frm) {
		frm.flag_public_attachments = true;
	}
});
