// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Submission Queue", {
	refresh: function (frm) {
		if (frm.doc.status === "Queued") {
			frm.add_custom_button(__("Unlock Reference Document"), () => {
				frm.call("unlock_doc");
			});
		}
	},
});
