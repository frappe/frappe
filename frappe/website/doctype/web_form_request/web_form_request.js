// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Web Form Request", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.key || !frm.doc.web_form) {
			return;
		}

		frm.add_custom_button(__("Copy Link"), () => {
			frappe.db.get_value("Web Form", frm.doc.web_form, "route").then(({ message }) => {
				const route = message.route || frm.doc.web_form;
				const key = encodeURIComponent(frm.doc.key);
				const url = frappe.urllib.get_full_url(`${route}/new?web_form_request_key=${key}`);
				frappe.utils.copy_to_clipboard(url, __("Web Form Request link copied"));
			});
		});
	},
});
