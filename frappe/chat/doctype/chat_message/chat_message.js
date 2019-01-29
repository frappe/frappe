// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Chat Message', {
	onload: function(frm) {
		if(frm.doc.type == 'File') {
			frm.set_df_property('content', 'read_only', 1);
		}
	}
});
