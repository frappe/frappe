// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Personal Data Deletion Request", {
	refresh: function (frm) {
		if (
			frappe.user.has_role("System Manager") &&
			(frm.doc.status == "Pending Approval" || frm.doc.status == "On Hold")
		) {
			frm.add_custom_button(__("Delete Data"), function () {
				return frappe.call({
					doc: frm.doc,
					method: "trigger_data_deletion",
					freeze: true,
					callback: function () {
						frm.refresh();
					},
				});
			});
		}

		if (frappe.user.has_role("System Manager") && frm.doc.status == "Pending Approval") {
			frm.add_custom_button(__("Put on Hold"), function () {
				return frappe.call({
					doc: frm.doc,
					method: "put_on_hold",
					callback: function () {
						frm.refresh();
					},
				});
			});
		}
	},
});
