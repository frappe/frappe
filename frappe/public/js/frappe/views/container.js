// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// page container
frappe.provide('frappe.pages');
frappe.provide('frappe.views');
frappe.provide('frappe.breadcrumbs');

frappe.views.Container = Class.extend({
	_intro: "Container contains pages inside `#container` and manages \
			page creation, switching",
	init: function() {
		this.container = $('#body_div').get(0);
		this.page = null; // current page
		this.pagewidth = $('#body_div').width();
		this.pagemargin = 50;

		var me = this;

		$(document).on("page-change", function() {
			// set data-route in body
			$("body").attr("data-route", frappe.get_route_str());
		});

		$(document).bind('rename', function(event, dt, old_name, new_name) {
			me.rename_breadcrumbs(dt, old_name, new_name)
		});
	},
	add_page: function(label) {
		var page = $('<div class="content page-container"></div>')
			.attr('id', "page-" + label)
			.attr("data-page-route", label)
			.toggle(false)
			.appendTo(this.container).get(0);
		page.label = label;
		frappe.pages[label] = page;

		return page;
	},
	change_to: function(label) {
		if(this.page && this.page.label === label) {
			$(this.page).trigger('show');
			return;
		}

		var me = this;
		if(label.tagName) {
			// if sent the div, get the table
			var page = label;
		} else {
			var page = frappe.pages[label];
		}
		if(!page) {
			console.log(__('Page not found')+ ': ' + label);
			return;
		}

		// hide dialog
		if(cur_dialog && cur_dialog.display && !cur_dialog.keep_open) {
			cur_dialog.hide();
		}

		// hide current
		if(this.page && this.page != page) {
			$(this.page).toggle(false);
			$(this.page).trigger('hide');
		}

		// show new
		if(!this.page || this.page != page) {
			this.page = page;
			// $(this.page).fadeIn(300);
			$(this.page).toggle(true);
		}

		$(document).trigger("page-change");

		this.page._route = window.location.hash;
		$(this.page).trigger('show');
		scroll(0,0);
		this.update_breadcrumbs();

		return this.page;
	},
	update_breadcrumbs: function() {
		var breadcrumbs = frappe.breadcrumbs[frappe.get_route_str()];
		var $breadcrumbs = $("#navbar-breadcrumbs").empty();
		if(!breadcrumbs) return;

		if(breadcrumbs.module && breadcrumbs.module != "Desk") {
			if(in_list(["Core", "Email", "Custom", "Workflow"], breadcrumbs.module))
				breadcrumbs.module = "Setup";
			var module_info = frappe.get_module(breadcrumbs.module),
				icon = module_info && module_info.icon,
				label = module_info ? module_info.label : breadcrumbs.module;

			if(module_info) {
				$(repl('<li><a href="#Module/%(module)s">%(label)s</a></li>',
					{ module: breadcrumbs.module, label: __(label) }))
					.appendTo($breadcrumbs);
			}

		}
		if(breadcrumbs.doctype) {
			$(repl('<li><a href="#List/%(doctype)s">%(label)s</a></li>',
				{doctype: breadcrumbs.doctype, label: __(breadcrumbs.doctype)}))
				.appendTo($breadcrumbs);
		}
	},
	rename_breadcrumbs: function(doctype, old_name, new_name) {
		var old_route_str = ["Form", doctype, old_name].join("/");
		var new_route_str = ["Form", doctype, new_name].join("/");
		frappe.breadcrumbs[new_route_str] = frappe.breadcrumbs[old_route_str];
		delete frappe.breadcrumbs[old_route_str];
	}
});

frappe.add_breadcrumbs = function(module, doctype) {
	frappe.breadcrumbs[frappe.get_route_str()] = {module:module, doctype:doctype};
	frappe.container.update_breadcrumbs();
}

