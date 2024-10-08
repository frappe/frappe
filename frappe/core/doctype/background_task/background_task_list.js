// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.listview_settings["Background Task"] = {
	get_indicator: function (doc) {
		var colors = {
			Queued: "yellow",
			"In Progress": "blue",
			Completed: "green",
			Failed: "red",
			Stopped: "grey",
		};
		let status = doc.status;
		return [__(status), colors[status], "status,=," + doc.status];
	},
};
