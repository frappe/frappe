// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Permission Request', {
	onload: (frm) => {
		frm.set_value_if_missing("user", frappe.session.user);
	},

	refresh: (frm) => {
		frm.set_query("authorizer", () => {
			return {
				filters: {
					email: ["!=", frappe.session.user],
					user_type: "System User"
				}
			}
		})
	}
});
