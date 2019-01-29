// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Personal Data Delete Request', {
	setup: function(frm) {
		frm.set_query("User", "email", function() {
			return {
				filters: {
					"email": ("not in", ["Administrator", "Guest"]),
				}
			}
		});
	},
	refresh: function(frm) {

	}
});
