wn.listview_settings['ToDo'] = {
	onload: function(me) {
		$(wn.container.page)
			.find(".layout-main-section")
			.css({
				"background-color":"cornsilk",
				"min-height": "400px"
			})
		if(user_roles.indexOf("System Manager")!==-1) {
			wn.route_options = {
				"owner": user
			}
		}
	}
}
