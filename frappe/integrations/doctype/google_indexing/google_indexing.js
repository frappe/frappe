// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Indexing', {
	refresh: function(frm) {
		if (!frm.doc.enable) {
			frm.dashboard.set_headline(__("To use Google API Indexing, enable {0}.", [`<a href='#Form/Google Settings'>${__('Google Settings')}</a>`]));
		}
	},

	authorize_api_indexing_access: function(frm) {
		let reauthorize = 0;
		if(frm.doc.authorization_code) {
			reauthorize = 1;
		}

		frappe.call({
			method: "frappe.integrations.doctype.google_indexing.google_indexing.authorize_access",
			args: {
				"g_contact": frm.doc.name,
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