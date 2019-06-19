// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Google Settings', {
	enable: function(frm) {
		frm.set_df_property('client_id', 'reqd', frm.doc.enable ? 1 : 0);
		frm.set_df_property('client_secret', 'reqd', frm.doc.enable ? 1 : 0);
	}
});
