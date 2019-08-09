// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Drive', {
	refresh: function(frm) {
		if (frm.is_new()) {
			frm.dashboard.set_headline(__("To use Google Drive, enable <a href='#Form/Google Settings'>Google Settings</a>."));
		}
	},
	authorize_google_drive_access: function(frm) {
		let reauthorize = 0;
		if(frm.doc.authorization_code) {
			reauthorize = 1;
		}

		frappe.call({
			method: "frappe.integrations.doctype.google_drive.google_drive.authorize_access",
			args: {
				"g_drive": frm.doc.name,
				"reauthorize": reauthorize
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
