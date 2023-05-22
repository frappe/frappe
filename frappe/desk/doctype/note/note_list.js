frappe.listview_settings["Note"] = {
	hide_name_column: true,
	add_fields: ["public"],
	get_indicator: function (doc) {
		if (doc.public) {
			return [__("Public"), "green", "public,=,Yes"];
		} else {
			return [__("Private"), "gray", "public,=,No"];
		}
	},
};
