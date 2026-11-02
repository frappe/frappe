// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Attachment Queue", {
	setup(frm) {
		frm.set_query("document_type", () => ({ filters: { enable_upload_first_workflow: 1 } }));
	},
});
