frappe.listview_settings['ToDo'] = {
	add_fields: ["`tabToDo`.`reference_type`", "`tabToDo`.reference_name"],
	add_columns: [{content:"Reference", label: __("Reference")}],
	prepare_data: function(data) {
		if (data.reference_type && data.reference_name) {
			data["Reference"] = repl('<a href="#Form/%(reference_type)s/%(reference_name)s">%(reference_type)s - %(reference_name)s</a>', data);
		}
	},
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
};
