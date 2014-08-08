frappe.listview_settings['ToDo'] = {
	onload: function(me) {
		frappe.route_options = {
			"owner": user,
			"status": "Open"
		};
	},
	add_fields: ["reference_type", "reference_name"],
	set_title_left: function() {
		frappe.set_route();
	}
}
