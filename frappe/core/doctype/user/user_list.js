// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.listview_settings['User'] = {
	prepare_data: function(data) {
		data["user_for_avatar"] = data["name"];
	}
};
