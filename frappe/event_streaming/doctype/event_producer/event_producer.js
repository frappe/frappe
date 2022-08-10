// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Event Producer", {
	refresh: function (frm) {
		frm.set_query("ref_doctype", "producer_doctypes", function () {
			return {
				filters: {
					issingle: 0,
					istable: 0,
				},
			};
		});

		frm.set_indicator_formatter("status", function (doc) {
			let indicator = "orange";
			if (doc.status == "Approved") {
				indicator = "green";
			} else if (doc.status == "Rejected") {
				indicator = "red";
			}
			return indicator;
		});
	},
});
