// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt


wn.provide("wn.ui")
wn.ui.app_icon = {
	get_html: function(app, small) {
		var icon = wn.modules[app].icon;
		var color = wn.modules[app].color;
		if(icon.split(".").slice(-1)[0]==="svg") {
			$.ajax({
				url: icon,
				dataType: "text",
				async: false,
				success: function(data) {
					icon = data;
				}
			})
			icon = '<object>'+icon+'</object>';
		} else {
			icon = '<i class="'+icon+'"></i>'
		}
		return '<div class="app-icon'+ (small ? " app-icon-small" : "")
			+'" style="background-color:'+color+'">'+icon+'</div>'
	}
}