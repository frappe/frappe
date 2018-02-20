// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Custom Script', {
	refresh: function(frm) {
		if (frm.doc.dt && frm.doc.script) {
			frm.add_web_link("/desk#List/" + encodeURIComponent(frm.doc.dt) + "/List", "Test Script");
		}
	}
});
