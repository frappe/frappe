// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("About Us Settings", {
	refresh: function (frm) {
		frm.set_intro(__('Link for About Us Page is "/about".'));
	},
});
