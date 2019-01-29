// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Personal Data Download Request', {
	setup: function(frm) {
		frm.set_query("user", function() {
			return {
				filters: {
					"name": ("not in", ["Administrator", "Guest"])
				}
			}
		});
	},
	refresh: function(frm) {

	}
});
