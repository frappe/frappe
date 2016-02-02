frappe.provide("frappe.ui.notifications")

frappe.ui.notifications.update_notifications = function() {
	frappe.ui.notifications.total = 0;
	var doctypes = keys(frappe.boot.notification_info.open_count_doctype).sort();
	var modules = keys(frappe.boot.notification_info.open_count_module).sort();
	var other = keys(frappe.boot.notification_info.open_count_other).sort();

	// clear toolbar / sidebar notifications
	frappe.ui.notifications.navbar_notification = $("#navbar-notification").empty();
	frappe.ui.notifications.sidebar_notification = $("#sidebar-notification").empty();

	// add these first.
	frappe.ui.notifications.add_notification("Comment");
	frappe.ui.notifications.add_notification("ToDo");
	frappe.ui.notifications.add_notification("Event");

	// add other
	$.each(other, function(i, name) {
		frappe.ui.notifications.add_notification(name, frappe.boot.notification_info.open_count_other);
	});


	// add a divider
	if(frappe.ui.notifications.total) {
		var divider = '<li class="divider"></li>';
		frappe.ui.notifications.navbar_notification.append($(divider));
		frappe.ui.notifications.sidebar_notification.append($(divider));
	}

	// add to toolbar and sidebar
	$.each(doctypes, function(i, doctype) {
		if(!in_list(["ToDo", "Comment", "Event"], doctype)) {
			frappe.ui.notifications.add_notification(doctype);
		}
	});

	// set click events
	$("#navbar-notification a, #sidebar-notification a").on("click", function() {
		var doctype = $(this).attr("data-doctype");
		var config = frappe.ui.notifications.config[doctype] || {};
		if (config.route) {
			frappe.set_route(config.route);
		} else if (config.click) {
			config.click();
		} else {
			frappe.views.show_open_count_list(this);
		}
	});

	// switch colour on the navbar
	$(".navbar-new-comments")
		.html(frappe.ui.notifications.total)
		.toggleClass("navbar-new-comments-true", frappe.ui.notifications.total ? true : false);

}

frappe.ui.notifications.add_notification = function(doctype, notifications_map) {
	if(!notifications_map) {
		notifications_map = frappe.boot.notification_info.open_count_doctype;
	}

	var count = notifications_map[doctype];
	if(count) {
		var config = frappe.ui.notifications.config[doctype] || {};
		var label = config.label || doctype;
		var notification_row = repl('<li><a class="badge-hover" data-doctype="%(data_doctype)s">\
			<span class="badge pull-right">\
				%(count)s</span> \
			%(label)s </a></li>', {
				label: __(label),
				icon: frappe.boot.doctype_icons[doctype],
				count: count,
				data_doctype: doctype
			});

		frappe.ui.notifications.navbar_notification.append($(notification_row));
		frappe.ui.notifications.sidebar_notification.append($(notification_row));

		frappe.ui.notifications.total += count;
	}
}

// default notification config
frappe.ui.notifications.config = {
	"ToDo": { label: __("To Do") },
	"Comment": { label: __("Messages"), route: "messages"},
	"Event": { label: __("Calendar"), route: "Calendar/Event" },
	"Likes": {
		label: __("Likes"),
		click: function() {
			frappe.route_options = {
				show_likes: true
			};

			if (frappe.get_route()[0]=="activity") {
				frappe.pages['activity'].on_page_show();
			} else {
				frappe.set_route("activity");
			}
		}
	}
};

frappe.views.show_open_count_list = function(element) {
	var doctype = $(element).attr("data-doctype");
	var condition = frappe.boot.notification_info.conditions[doctype];

	if(condition && $.isPlainObject(condition)) {
		frappe.route_options = condition;
	}

	var route = frappe.get_route();
	if(route[0]==="List" && route[1]===doctype) {
		frappe.pages["List/" + doctype].doclistview.refresh();
	} else {
		frappe.set_route("List", doctype);
	}
}
