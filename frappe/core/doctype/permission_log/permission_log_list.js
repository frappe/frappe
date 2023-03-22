frappe.listview_settings["Permission Log"] = {
	hide_name_column: true,
	add_fields: ["action"],

	get_indicator(doc) {
		if (doc.action === "Create") {
			return ["Create", "blue"];
		} else if (doc.action === "Update") {
			return ["Update", "darkgrey"];
		} else {
			return ["Remove", "red"];
		}
	},

	onload(listview) {
		if (listview.list_view_settings) {
			listview.list_view_settings.disable_comment_count = 1;
		}
	},
};
