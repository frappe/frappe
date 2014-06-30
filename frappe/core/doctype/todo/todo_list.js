frappe.listview_settings['ToDo'] = {
	onload: function(me) {
		frappe.route_options = {
			"status": "Open",
			"owner": user
		};
	},
	set_title_left: function() {
		frappe.set_route();
	},

	add_columns: [
		{"content": "Assigned To", width:"15%", label: "Assigned To"}
	],

	prepare_data: function(data) {
		data["user_for_avatar"] = data.owner;
		data["Assigned To"] = data.owner===user ? null : (frappe.boot.user_info[data.owner] || {}).fullname;
	}
}
