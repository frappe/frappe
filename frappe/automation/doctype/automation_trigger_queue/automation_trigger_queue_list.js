frappe.listview_settings["Automation Trigger Queue"] = {
	add_fields: ["run_after"],
	get_indicator: function (doc) {
		var colors = {
			Pending: "orange",
			Scheduled: "purple",
			Running: "blue",
			Done: "green",
			Failed: "red",
			Skipped: "gray",
		};
		var label = __(doc.status);
		if (doc.status === "Scheduled" && doc.run_after) {
			label = __("Scheduled for {0}", [frappe.datetime.str_to_user(doc.run_after)]);
		}
		return [label, colors[doc.status], "status,=," + doc.status];
	},
};
