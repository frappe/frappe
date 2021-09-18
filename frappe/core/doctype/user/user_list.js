// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings['User'] = {
	add_fields: ["enabled", "user_type", "user_image"],
	filters: [["enabled","=",1]],
	prepare_data: function(data) {
		data["user_for_avatar"] = data["name"];
	},
	get_indicator: function(doc) {
		if(doc.enabled) {
			return [__("Active"), "green", "enabled,=,1"];
		} else {
			return [__("Disabled"), "grey", "enabled,=,0"];
		}
	}
};

frappe.help.youtube_id["User"] = "8Slw1hsTmUI";
