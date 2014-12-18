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

		$(document).on("page-change", this.set_full_width);
	},
	add_page: function(label, onshow, onhide) {
		var page = $('<div class="content page-container"></div>')
			.attr('id', "page-" + label)
			.attr("data-page-route", label)
			.toggle(false)
			.appendTo(this.container).get(0);
		if(onshow)
			$(page).bind('show', onshow);
		if(onshow)
			$(page).bind('hide', onhide);
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
			//$(this.page).fadeIn();
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

		var divider = function() {
			$('<li style="padding: 8px 0px"><i class="icon-chevron-right text-muted"></i></li>').appendTo($breadcrumbs);
		}

		if(breadcrumbs.module) {
			divider();
			$('<li><a href="#Module/'+ breadcrumbs.module +'">'+ __(breadcrumbs.module) +'</a></li>').appendTo($breadcrumbs);
		}
		if(breadcrumbs.doctype) {
			divider();
			$('<li><a href="#List/'+ breadcrumbs.doctype +'">'+ __(breadcrumbs.doctype) +'</a></li>').appendTo($breadcrumbs);
		}
	},
	set_full_width: function() {
		// limit max-width to 970px for most pages
		$("body").toggleClass("limit-container-width", !$(frappe.container.page).find(".app-page.full-width").length);
	}
});

frappe.add_breadcrumbs = function(module, doctype) {
	frappe.breadcrumbs[frappe.get_route_str()] = {module:module, doctype:doctype};
	frappe.container.update_breadcrumbs();
}

