// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('User Permission', {
	setup: function(frm) {
		frm.set_query("allow", function() {
			return {
				"filters": {
					issingle: 0,
					istable: 0
				}
			};
		});
	},

	refresh: function(frm) {
		frm.add_custom_button(__('View Permitted Documents'),
			() => frappe.set_route('query-report', 'Permitted Documents For User',
				{user: frm.doc.user}));
	}
});
