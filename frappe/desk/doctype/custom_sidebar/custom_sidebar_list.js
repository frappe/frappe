// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.listview_settings["Custom Sidebar"] = {
	add_fields: ["user"],
	// The site layer by default: this list is where a Workspace Manager audits what *this
	// site* has said about its navigation, and every user's personal arrangement lives in the
	// same table. Clear the filter to see those too.
	filters: [["user", "=", ""]],
	get_indicator(doc) {
		return doc.user ? [__("User"), "gray", "user,!=,"] : [__("Site"), "blue", "user,=,"];
	},
};
