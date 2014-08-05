// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings['User'] = {
	add_fields: ["enabled", "first_name", "last_name", "user_type"],
	filters: [["enabled","=","Yes"], ["user_type","=","System User"]],
	prepare_data: function(data) {
		data["user_for_avatar"] = data["name"];
	}
};
