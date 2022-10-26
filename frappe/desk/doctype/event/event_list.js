frappe.listview_settings["Event"] = {
	add_fields: ["starts_on", "ends_on", "status"],
	get_indicator: function(doc) {
		if (doc.status === "Closed") {
			return [__("Closed"), "green", "status,=,Closed"];
		}, else if (doc.status === "Completed") {
			return [__("Completed"), "green", "status,=,Completed"];
		} else if (doc.status === "Open") {
			return [__("Open"), "red", "status,=,Open"];
		}
	},
	onload: function () {
		frappe.route_options = {
			status: "Open",
		};
	},
};
