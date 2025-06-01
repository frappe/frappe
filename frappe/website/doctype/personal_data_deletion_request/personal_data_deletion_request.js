// Copyright (c) 2019, nts Technologies and contributors
// For license information, please see license.txt

nts.ui.form.on("Personal Data Deletion Request", {
	refresh: function (frm) {
		if (
			nts.user.has_role("System Manager") &&
			(frm.doc.status == "Pending Approval" || frm.doc.status == "On Hold")
		) {
			frm.add_custom_button(__("Delete Data"), function () {
				return nts.call({
					doc: frm.doc,
					method: "trigger_data_deletion",
					freeze: true,
					callback: function () {
						frm.refresh();
					},
				});
			});
		}

		if (nts.user.has_role("System Manager") && frm.doc.status == "Pending Approval") {
			frm.add_custom_button(__("Put on Hold"), function () {
				return nts.call({
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
