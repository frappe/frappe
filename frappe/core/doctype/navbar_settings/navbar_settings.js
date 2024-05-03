// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Navbar Settings", {
	after_save: function (frm) {
		frappe.ui.toolbar.clear_cache();
	},
});
