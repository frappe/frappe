// Copyright (c) 2016, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Email Queue", {
	refresh: function (frm) {
		if (["Not Sent", "Partially Sent"].includes(frm.doc.status)) {
			let button = frm.add_custom_button("Send Now", function () {
				nts.call({
					method: "nts.email.doctype.email_queue.email_queue.send_now",
					args: {
						name: frm.doc.name,
						force_send: true,
					},
					btn: button,
					callback: function () {
						frm.reload_doc();
						if (cint(nts.sys_defaults.suspend_email_queue)) {
							nts.show_alert(
								__(
									"Email queue is currently suspended. Resume to automatically send other emails."
								)
							);
						}
					},
				});
			});
		} else if (frm.doc.status == "Error") {
			frm.add_custom_button("Retry Sending", function () {
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
