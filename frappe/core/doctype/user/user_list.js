// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings["User"] = {
	add_fields: ["enabled", "user_type", "user_image"],
	filters: [["enabled", "=", 1]],
	onload(listview) {
		this.set_default_app_options(listview);
	},
	prepare_data: function (data) {
		data["user_for_avatar"] = data["name"];
	},
	get_indicator: function (doc) {
		if (doc.enabled) {
			return [__("Active"), "green", "enabled,=,1"];
		} else {
			return [__("Disabled"), "grey", "enabled,=,0"];
		}
	},
	set_default_app_options(listview) {
		const default_app_field = frappe.meta.get_docfield("User", "default_app");
		if (!default_app_field) return;

		frappe.xcall("frappe.apps.get_apps").then((r) => {
			let apps = r?.map((r) => r.name) || [];
			default_app_field.options = ["", ...apps].join("\n");
		});
	},
};

frappe.help.youtube_id["User"] = "8Slw1hsTmUI";
