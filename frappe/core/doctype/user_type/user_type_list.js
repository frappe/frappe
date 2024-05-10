frappe.listview_settings["User Type"] = {
	add_fields: ["is_standard"],
	get_indicator: function (doc) {
		if (doc.is_standard) {
			return [__("Standard"), "green", "is_standard,=,1"];
		} else {
			return [__("Custom"), "blue", "is_standard,=,0"];
		}
	},
};
