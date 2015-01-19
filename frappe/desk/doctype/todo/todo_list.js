frappe.listview_settings['ToDo'] = {
	onload: function(me) {
		frappe.route_options = {
			"owner": user,
			"status": "Open"
		};
		me.page.set_title(__("To Do"));
	},
	add_fields: ["reference_type", "reference_name"],
}
