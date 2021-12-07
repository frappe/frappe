// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Personal Data Deletion Request", {
	refresh: function(frm) {
		if (
			frappe.user.has_role("System Manager") &&
			frm.doc.status == "Pending Approval"
		) {
			frm.add_custom_button(__("Delete Data"), function() {
				return frappe.call({
					doc: frm.doc,
					method: "trigger_data_deletion",
					freeze: true,
					callback: function() {
						frm.refresh();
					}
				});
			});
		}
	},

	before_load: function(frm) {
		frappe.db.get_single_value("Website Settings", "account_deletion_sla").then((data) => {
			if (data < 1) {
				frm.set_df_property("sla_status", "hidden", 1);
			}
		});
	}
});
