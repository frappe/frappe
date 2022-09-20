frappe.listview_settings["Web Form"] = {
	add_fields: ["title", "published"],
	get_indicator: function (doc) {
		if (doc.published) {
			return [__("Published"), "green", "published,=,1"];
		} else {
			return [__("Not Published"), "gray", "published,=,0"];
		}
	},
};
