frappe.ui.form.on("Bulk Email", {
	refresh: function(frm) {
		if (frm.doc.status==="Not Sent") {
			frm.add_custom_button("Send Now", function() {
				frappe.call({
					method: 'frappe.email.doctype.bulk_email.bulk_email.send_now',
					args: {
						name: frm.doc.name
					},
					callback: function() {
						frm.reload_doc();
					}
				});
			});
		}

		if (frm.doc.status==="Error") {
			frm.add_custom_button("Retry Sending", function() {
				frm.call({
					method: "retry_sending",
					args: {
						name: frm.doc.name
					},
					callback: function(r) {
						if (!r.exc) {
							frm.set_value("status", "Not Sent");
						}
					}
				})
			});
		}
	}
});
