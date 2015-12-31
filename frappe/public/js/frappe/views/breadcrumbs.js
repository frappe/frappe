// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.breadcrumbs = {
	all: {},

	preferred: {
		"File": ""
	},

	set_doctype_module: function(doctype, module) {
		localStorage["preferred_breadcrumbs:" + doctype] = module;
	},

	get_doctype_module: function(doctype) {
		return localStorage["preferred_breadcrumbs:" + doctype];
	},

	add: function(module, doctype, type) {
		frappe.breadcrumbs.all[frappe.get_route_str()] = {module:module, doctype:doctype, type:type};
		frappe.breadcrumbs.update();
	},

	update: function() {
		var breadcrumbs = frappe.breadcrumbs.all[frappe.get_route_str()];

		var $breadcrumbs = $("#navbar-breadcrumbs").empty();
		if(!breadcrumbs) {
			$("body").addClass("no-breadcrumbs");
			return;
		}

		// get preferred module for breadcrumbs, based on sent via module
		var from_module = frappe.breadcrumbs.get_doctype_module(breadcrumbs.doctype);

		if(from_module) {
			breadcrumbs.module = from_module;
		} else if(frappe.breadcrumbs.preferred[breadcrumbs.doctype]!==undefined) {
			// get preferred module for breadcrumbs
			breadcrumbs.module = frappe.breadcrumbs.preferred[breadcrumbs.doctype];
		}

		if(breadcrumbs.module && breadcrumbs.module != "Desk") {
			if(in_list(["Core", "Email", "Custom", "Workflow", "Print"], breadcrumbs.module))
				breadcrumbs.module = "Setup";

			if(frappe.user.modules.indexOf(breadcrumbs.module)!==-1) {
				// if module access exists
				var module_info = frappe.get_module(breadcrumbs.module),
					icon = module_info && module_info.icon,
					label = module_info ? module_info.label : breadcrumbs.module;

				if(module_info) {
					$(repl('<li><a href="#Module/%(module)s">%(label)s</a></li>',
						{ module: breadcrumbs.module, label: __(label) }))
						.appendTo($breadcrumbs);
				}
			}

		}
		if(breadcrumbs.doctype && frappe.get_route()[0]==="Form") {
			if(breadcrumbs.doctype==="User" && frappe.user.modules.indexOf("Setup")===-1) {
				// no user listview for non-system managers
			} else {
				route = (cur_frm && cur_frm.list_route) || ("List/" + breadcrumbs.doctype)
				$(repl('<li><a href="#%(route)s">%(label)s</a></li>',
					{route: route, label: __(breadcrumbs.doctype)}))
					.appendTo($breadcrumbs);
			}
		}

		$("body").removeClass("no-breadcrumbs");
	},

	rename: function(doctype, old_name, new_name) {
		var old_route_str = ["Form", doctype, old_name].join("/");
		var new_route_str = ["Form", doctype, new_name].join("/");
		frappe.breadcrumbs.all[new_route_str] = frappe.breadcrumbs.all[old_route_str];
		delete frappe.breadcrumbs.all[old_route_str];
	}

}

