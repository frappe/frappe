// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.breadcrumbs = {
	all: {},

	preferred: {
		"File": "",
		"Dashboard": "Customization",
		"Dashboard Chart": "Customization",
		"Dashboard Chart Source": "Customization"
	},

	module_map: {
		'Core': 'Settings',
		'Email': 'Settings',
		'Custom': 'Settings',
		'Workflow': 'Settings',
		'Printing': 'Settings',
		'Setup': 'Settings',
		'Event Streaming': 'Tools',
		'Automation': 'Tools',
	},

	set_doctype_module: function(doctype, module) {
		localStorage["preferred_breadcrumbs:" + doctype] = module;
	},

	get_doctype_module: function(doctype) {
		return localStorage["preferred_breadcrumbs:" + doctype];
	},

	add: function(module, doctype, type) {
		let obj;
		if (typeof module === 'object') {
			obj = module;
		} else {
			obj = {
				module:module,
				doctype:doctype,
				type:type
			}
		}

		frappe.breadcrumbs.all[frappe.breadcrumbs.current_page()] = obj;
		frappe.breadcrumbs.update();
	},

	current_page: function() {
		return frappe.get_route_str();
	},

	update: function() {
		var breadcrumbs = frappe.breadcrumbs.all[frappe.breadcrumbs.current_page()];

		if(!frappe.visible_modules) {
			frappe.visible_modules = $.map(frappe.boot.allowed_modules, (m) => {
				return m.module_name;
			});
		}

		var $breadcrumbs = $("#navbar-breadcrumbs").empty();

		if(!breadcrumbs) {
			$("body").addClass("no-breadcrumbs");
			return;
		}

		if (breadcrumbs.type === 'Custom') {
			const html = `<li><a href="${breadcrumbs.route}">${breadcrumbs.label}</a></li>`;
			$breadcrumbs.append(html);
			$("body").removeClass("no-breadcrumbs");
			return;
		}

		// get preferred module for breadcrumbs, based on sent via module
		var from_module = frappe.breadcrumbs.get_doctype_module(breadcrumbs.doctype);

		if (from_module) {
			breadcrumbs.module = from_module;
		} else if(frappe.breadcrumbs.preferred[breadcrumbs.doctype]!==undefined) {
			// get preferred module for breadcrumbs
			breadcrumbs.module = frappe.breadcrumbs.preferred[breadcrumbs.doctype];
		}

		if (breadcrumbs.module) {
			if (frappe.breadcrumbs.module_map[breadcrumbs.module]) {
				breadcrumbs.module = frappe.breadcrumbs.module_map[breadcrumbs.module];
			}

			let current_module = breadcrumbs.module
			// Check if a desk page exists
			if (frappe.boot.module_page_map[breadcrumbs.module]) {
				breadcrumbs.module = frappe.boot.module_page_map[breadcrumbs.module];
			}

			if (frappe.get_module(current_module)) {
				// if module access exists
				var module_info = frappe.get_module(current_module),
					icon = module_info && module_info.icon,
					label = module_info ? module_info.label : breadcrumbs.module;

				if(module_info && !module_info.blocked && frappe.visible_modules.includes(module_info.module_name)) {
					$(repl('<li><a href="/app/workspace/%(module)s">%(label)s</a></li>',
						{ module: breadcrumbs.module, label: __(breadcrumbs.module) }))
						.appendTo($breadcrumbs);
				}
			}
		}

		let set_list_breadcrumb = (doctype) => {
			if ((doctype==="User" && !frappe.user.has_role('System Manager'))
				|| frappe.get_doc('DocType', doctype).issingle) {
				// no user listview for non-system managers and single doctypes
			} else {
				let route;
				const doctype_route = frappe.router.slug(frappe.router.doctype_layout || breadcrumbs.doctype);
				if (frappe.boot.treeviews.indexOf(breadcrumbs.doctype) !== -1) {
					let view = frappe.model.user_settings[breadcrumbs.doctype].last_view || 'Tree';
					route = `${doctype_route}/view/${view}`;
				} else {
					route = doctype_route;
				}
				$(`<li><a href="/app/${route}">${doctype}</a></li>`)
					.appendTo($breadcrumbs)
			}
		}

		let set_form_breadcrumb = (doctype) => {
			let docname = frappe.get_route()[2];
			let form_route = `/app/${frappe.router.slug(doctype)}/${docname}`;
			$(`<li><a href="${form_route}">${docname}</a></li>`)
				.appendTo($breadcrumbs);
		}

		const route = frappe.get_route()[0].toLowerCase();
		if (breadcrumbs.doctype && ["print", "form"].includes(route)) {
			set_list_breadcrumb(breadcrumbs.doctype);
			set_form_breadcrumb(breadcrumbs.doctype);
			route == "form" && $breadcrumbs.find('li').last().addClass('disabled');
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

