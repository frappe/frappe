// Copyright (c) 2020, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Log Settings", {
	refresh: (frm) => {
		frm.set_query("ref_doctype", "logs_to_clear", () => {
			const added_doctypes = frm.doc.logs_to_clear.map((r) => r.ref_doctype);
			return {
				query: "frappe.core.doctype.log_settings.log_settings.get_log_doctypes",
				filters: [["name", "not in", added_doctypes]],
			};
		});
	},
});
