// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.toolbar");

frappe.ui.toolbar.Toolbar = Class.extend({
	init: function() {
		var header = $('header').append(frappe.render_template("navbar", {}));
		var sidebar = $('.offcanvas .sidebar-left').append(frappe.render_template("offcanvas_left_sidebar", {}));

		header.find(".toggle-sidebar").on("click", function() {
			$(".offcanvas").toggleClass("active-left").removeClass("active-right");
			return false;
		});

		header.find(".toggle-navbar-new-comments").on("click", function() {
			$(".offcanvas").toggleClass("active-right").removeClass("active-left");
			return false;
		});

		$(document).on("notification-update", function() {
			frappe.ui.toolbar.update_notifications();
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
	},
})

frappe.ui.toolbar.update_notifications = function() {
	var total = 0;
	var doctypes = keys(frappe.boot.notification_info.open_count_doctype).sort();
	var modules = keys(frappe.boot.notification_info.open_count_module).sort();

	var navbar_notification = $("#navbar-notification").empty();
	var sidebar_notification = $("#sidebar-notification").empty();

	$.each(modules, function(i, module) {
		var count = frappe.boot.notification_info.open_count_module[module];
		if(count) {
			var notification_row = repl('<li><a class="badge-hover" data-module="%(data_module)s">\
				<span class="badge pull-right">\
					%(count)s</span> \
				%(module)s </a></li>', {
					module: __(module),
					count: count,
					icon: frappe.modules[module].icon,
					data_module: module
				});

			navbar_notification.append($(notification_row));
			sidebar_notification.append($(notification_row));

			total += count;
		}
	});

	if(total) {
		var divider = '<li class="divider"></li>';
		navbar_notification.append($(divider));
		sidebar_notification.append($(divider));
	}

	$.each(doctypes, function(i, doctype) {
		var count = frappe.boot.notification_info.open_count_doctype[doctype];
		if(count) {
			var notification_row = repl('<li><a class="badge-hover" data-doctype="%(data_doctype)s">\
				<span class="badge pull-right">\
					%(count)s</span> \
				%(doctype)s </a></li>', {
					doctype: __(doctype),
					icon: frappe.boot.doctype_icons[doctype],
					count: count,
					data_doctype: doctype
				});

			navbar_notification.append($(notification_row));
			sidebar_notification.append($(notification_row));

			total += count;
		}
	});

	$("#navbar-notification a, #sidebar-notification a").on("click", function() {
		var module = $(this).attr("data-module");
		if (module) {
			frappe.set_route(frappe.modules[module].link);
		} else {
			var doctype = $(this).attr("data-doctype");
			if (doctype) {
				frappe.views.show_open_count_list(this);
			}
		}
		return false;
	});

	$(".navbar-new-comments")
		.html(total)
		.toggleClass("navbar-new-comments-true", total ? true : false);

}

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

frappe.views.show_open_count_list = function(element) {
	var doctype = $(element).attr("data-doctype");
	var condition = frappe.boot.notification_info.conditions[doctype];
	if(condition) {
		frappe.route_options = condition;
		var route = frappe.get_route();
		if(route[0]==="List" && route[1]===doctype) {
			frappe.pages["List/" + doctype].doclistview.refresh();
		} else {
			frappe.set_route("List", doctype);
		}
	}
}
