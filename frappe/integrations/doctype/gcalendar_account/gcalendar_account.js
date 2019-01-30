// Copyright (c) 2018, DOKOS and contributors
// For license information, please see license.txt

frappe.ui.form.on('GCalendar Account', {
	allow_google_access: function(frm) {
		frappe.call({
			method: "frappe.integrations.doctype.gcalendar_settings.gcalendar_settings.google_callback",
			args: {
				'account': frm.doc.name
			},
			callback: function(r) {
				if(!r.exc) {
					frm.save();
					window.open(r.message.url);
				}
			}
		});
	}
});
