// Copyright (c) 2023, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Form Tour Settings", {
	refresh(frm) {
		frm.dashboard.add_comment(
			"This page is used to set priority for the UI form tours. If there are more than 1 matching tours found for the page, the tour with the highest priority will run.",
			"blue",
			true
		);
	},
});
