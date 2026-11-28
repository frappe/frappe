// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Address Template", {
	refresh: function (frm) {
		if (frm.is_new() && !frm.doc.template && frappe.user.is_code_author()) {
			// set default template via js so that it is translated; others get it on save
			frappe.call({
				method: "frappe.contacts.doctype.address_template.address_template.get_default_address_template",
				type: "GET",
				callback: function (r) {
					frm.set_value("template", r.message);
				},
			});
		}
	},
});
