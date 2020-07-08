// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings['User'] = {
	add_fields: ["enabled", "user_type", "user_image", "suspend_all_auto_assignments"],
	filters: [["enabled","=",1]],
	prepare_data: function(data) {
		data["user_for_avatar"] = data["name"];
	},
	get_indicator: function(doc) {
		if (doc.suspend_all_auto_assignments && doc.enabled) {
			return [__("Unavailable For Assignments"), "yellow", "enabled,=,1"];
		} else if (doc.enabled) {
			return [__("Active"), "green", "enabled,=,1"];
		} else {
			return [__("Disabled"), "grey", "enabled,=,0"];
		}
	}
};

frappe.help.youtube_id["User"] = "8Slw1hsTmUI";
