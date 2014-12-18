// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt


frappe.ui.toolbar.Toolbar = Class.extend({
	init: function() {
		$('header').append(frappe.render(frappe.templates.navbar, {}));

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

	$("#navbar-notification").empty();

	$.each(modules, function(i, module) {
		var count = frappe.boot.notification_info.open_count_module[module];
		if(count) {
			$(repl('<li><a>\
				<span class="badge pull-right">\
					%(count)s</span> \
				<i class="icon-fixed-width %(icon)s"></i> %(module)s </a></li>', {
					module: __(module),
					count: count,
					icon: frappe.modules[module].icon
				}))
				.appendTo("#navbar-notification")
					.find("a")
					.attr("data-module", module)
					.css({"min-width":"200px"})
					.on("click", function() {
						frappe.set_route(frappe.modules[$(this).attr("data-module")].link);
					});
			total += count;
		}
	});

	if(total) {
		$('<li class="divider"></li>').appendTo("#navbar-notification");
	}

	$.each(doctypes, function(i, doctype) {
		var count = frappe.boot.notification_info.open_count_doctype[doctype];
		if(count) {
			$(repl('<li><a>\
				<span class="badge pull-right">\
					%(count)s</span> \
				<i class="icon-fixed-width %(icon)s"></i> %(doctype)s </a></li>', {
					doctype: __(doctype),
					icon: frappe.boot.doctype_icons[doctype],
					count: count
				}))
				.appendTo("#navbar-notification")
					.find("a")
					.attr("data-doctype", doctype)
					.css({"min-width":"200px"})
					.on("click", function() {
						frappe.views.show_open_count_list(this);
					});
			total += count;
		}
	});

	$(".navbar-new-comments")
		.html(total)
		.toggleClass("navbar-new-comments-true", total ? true : false);

}

frappe.ui.toolbar.clear_cache = function() {
	localStorage && localStorage.clear();
	$c('frappe.sessions.clear',{},function(r,rt){
		if(!r.exc) {
			show_alert(r.message);
			location.reload();
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
