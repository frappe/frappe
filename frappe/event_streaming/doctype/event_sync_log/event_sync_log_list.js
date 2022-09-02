frappe.listview_settings["Event Sync Log"] = {
	get_indicator: function (doc) {
		var colors = {
			Failed: "red",
			Synced: "green",
		};
		return [__(doc.status), colors[doc.status], "status,=," + doc.status];
	},
};
