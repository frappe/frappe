// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings['User'] = {
	add_fields: ["enabled", "user_type"],
	filters: [["enabled","=","Yes"], ["user_type","=","System User"]],
	prepare_data: function(data) {
		data["user_for_avatar"] = data["name"];
	},
	get_indicator: function(doc) {
		if(doc.enabled) {
			return [__("Active"), "green", "enabled,=,Yes"];
		} else {
			return [__("Disabled"), "grey", "enabled,=,No"];
		}
	}
};
