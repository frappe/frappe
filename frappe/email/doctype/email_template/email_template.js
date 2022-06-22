// Copyright (c) 2018, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Email Template', {
	refresh: function() {

	},

	use_html: function(frm) {
		frm.set_df_property("response_html", "reqd", frm.doc.use_html);
		frm.set_df_property("response", "reqd", !frm.doc.use_html);
	}
});
