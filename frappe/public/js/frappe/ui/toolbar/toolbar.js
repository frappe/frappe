// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.toolbar");

frappe.ui.toolbar.Toolbar = Class.extend({
	init: function() {
		var header = $('header').append(frappe.render_template("navbar", {
			avatar: frappe.avatar(frappe.session.user)
		}));

		header.find(".toggle-sidebar").on("click", function () {
			var layout_side_section = $('.layout-side-section');
			var overlay_sidebar = layout_side_section.find('.overlay-sidebar');
			overlay_sidebar.addClass('opened');
			overlay_sidebar.find('.reports-dropdown').removeClass('dropdown-menu').addClass('list-unstyled');
			overlay_sidebar.find('.dropdown-toggle').addClass('text-muted').find('.caret').addClass('hidden-xs hidden-sm');

			$('<div class="close-sidebar">').hide().appendTo(layout_side_section).fadeIn();

			var scroll_container = $('html');
			scroll_container.css("overflow-y", "hidden");

			layout_side_section.find(".close-sidebar").on('click', close_sidebar);
			layout_side_section.on("click", "a", close_sidebar);

			function close_sidebar(e) {
				scroll_container.css("overflow-y", "");

				layout_side_section.find(".close-sidebar").fadeOut(function() {
					overlay_sidebar.removeClass('opened').find('.dropdown-toggle').removeClass('text-muted');
					overlay_sidebar.find('.reports-dropdown').addClass('dropdown-menu');
				});
			}
		});

		$(document).on("notification-update", function() {
			frappe.ui.notifications.update_notifications();
		});

		$('.dropdown-toggle').dropdown();

		$(document).trigger('toolbar_setup');

		// clear all custom menus on page change
		$(document).on("page-change", function() {
			$("header .navbar .custom-menu").remove();
		});

		frappe.search.setup();
	},

});

$.extend(frappe.ui.toolbar, {
	add_dropdown_button: function(parent, label, click, icon) {
		var menu = frappe.ui.toolbar.get_menu(parent);
		if(menu.find("li:not(.custom-menu)").length && !menu.find(".divider").length) {
			frappe.ui.toolbar.add_menu_divider(menu);
		}

		return $('<li class="custom-menu"><a><i class="icon-fixed-width '
			+icon+'"></i> '+label+'</a></li>')
			.insertBefore(menu.find(".divider"))
			.find("a")
			.click(function() {
				click.apply(this);
			});
	},
	get_menu: function(label) {
		return $("#navbar-" + label.toLowerCase());
	},
	add_menu_divider: function(menu) {
		menu = typeof menu == "string" ?
			frappe.ui.toolbar.get_menu(menu) : menu;

		$('<li class="divider custom-menu"></li>').prependTo(menu);
	}
});

frappe.ui.toolbar.clear_cache = function() {
	frappe.assets.clear_local_storage();
	$c('frappe.sessions.clear',{},function(r,rt){
		if(!r.exc) {
			show_alert(r.message);
			location.reload(true);
		}
	});
	return false;
}

frappe.ui.toolbar.download_backup = function() {
	msgprint(__("Your download is being built, this may take a few moments..."));
	return $c('frappe.utils.backups.get_backup',{},function(r,rt) {});
	return false;
}

frappe.ui.toolbar.show_about = function() {
	try {
		frappe.ui.misc.about();
	} catch(e) {
		console.log(e);
	}
	return false;
}
