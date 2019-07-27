frappe.listview_settings['Event'] = {
	add_fields: ["starts_on", "ends_on"],
	onload: function(listview) {
		frappe.route_options = {
			"status": "Open"
		};
	}
}