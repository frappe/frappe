// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Email Queue", {
	refresh: function (frm) {
		if (["Not Sent", "Partially Sent"].includes(frm.doc.status)) {
			let button = frm.add_custom_button("Send Now", function () {
				frappe.call({
					method: "frappe.email.doctype.email_queue.email_queue.send_now",
					args: {
						name: frm.doc.name,
					},
					btn: button,
					callback: function () {
						frm.reload_doc();
					},
				});
			});
		} else if (frm.doc.status == "Error") {
			frm.add_custom_button(__("Retry Sending"), function () {
				frm.call({
					method: "retry_sending",
					doc: frm.doc,
					args: {
						name: frm.doc.name,
					},
					callback: function () {
						frm.reload_doc();
					},
				});
			});
		}
	},
});
