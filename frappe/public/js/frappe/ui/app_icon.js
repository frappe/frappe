// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt


frappe.provide("frappe.ui")
frappe.ui.app_icon = {
	get_html: function(app, small) {
		var icon = frappe.modules[app].icon;
		var color = frappe.modules[app].color;
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
			icon = '<i class="'+icon+'" style="color: ' + color + '"></i>';
		}
		return '<div class="app-icon'+ (small ? " app-icon-small" : "")
			+'" style="border: 2px solid '+color+'">'+icon+'</div>'
	}
}
