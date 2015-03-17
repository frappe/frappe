// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt


frappe.provide("frappe.ui")
frappe.ui.app_icon = {
	get_html: function(app, small, modules) {
		if(!modules) {
			modules = frappe.modules;
		}

		var icon = modules[app].icon;
		var color = modules[app].color;
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
			icon = '<i class="'+icon+'"></i>';
		}
		return '<div class="app-icon'+ (small ? " app-icon-small" : "")
			+'" style="background-color: '+ color +'">'+icon+'</div>'
	}
}
