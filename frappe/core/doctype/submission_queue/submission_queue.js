// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Submission Queue", {
	setup: frappe.realtime.on("termination_status", (data) => {
		let color = "green";
		if (data.status == "Failed") {
			color = "orange";
		}
		frappe.show_alert({
			message: data.message,
			indicator: color,
		});
	}),
	refresh: function (frm) {
		if (frm.doc.status === "Queued") {
			frm.add_custom_button(__("Unlock Reference Document"), () => {
				frm.call("unlock_doc");
			});
		}
	},
});
