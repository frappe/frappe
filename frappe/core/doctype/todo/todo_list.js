frappe.listview_settings['ToDo'] = {
	onload: function(me) {
		$(frappe.container.page)
			.find(".layout-main-section")
			.css({
				"background-color":"cornsilk",
				"min-height": "400px"
			})
		if(user_roles.indexOf("System Manager")!==-1) {
			frappe.route_options = {
				"owner": user
			}
		}
	},
	set_title_left: function() {
		frappe.set_route();
	}
}
