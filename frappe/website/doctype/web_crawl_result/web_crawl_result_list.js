// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.listview_settings["Web Crawl Result"] = {
	add_fields: ["error", "change_status"],
	get_indicator(doc) {
		if (doc.error) {
			return [__("Failed"), "red", "error,is,set"];
		}
		if (!doc.change_status) return;
		const colors = { New: "blue", Changed: "orange", Unchanged: "gray" };
		return [
			__(doc.change_status),
			colors[doc.change_status],
			`change_status,=,${doc.change_status}`,
		];
	},
	hide_name_column: true,
};
