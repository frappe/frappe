frappe.provide("frappe.ui.notifications")

frappe.ui.notifications.update_notifications = function() {
	frappe.ui.notifications.total = 0;
	var doctypes = keys(frappe.boot.notification_info.open_count_doctype).sort();
	var modules = keys(frappe.boot.notification_info.open_count_module).sort();
	var other = keys(frappe.boot.notification_info.open_count_other).sort();

	// clear toolbar / sidebar notifications
	frappe.ui.notifications.dropdown_notification = $("#dropdown-notification").empty();

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
		frappe.ui.notifications.dropdown_notification.append($(divider));
	}

	// add to toolbar and sidebar
	$.each(doctypes, function(i, doctype) {
		if(!in_list(["ToDo", "Comment", "Event"], doctype)) {
			frappe.ui.notifications.add_notification(doctype);
		}
	});

	// set click events
	$("#dropdown-notification a").on("click", function() {
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

	// switch colour on the navbar and disable if no notifications
	$(".navbar-new-comments")
		.html(frappe.ui.notifications.total > 20 ? '20+' : frappe.ui.notifications.total)
		.toggleClass("navbar-new-comments-true", frappe.ui.notifications.total ? true : false)
		.parent().toggleClass("disabled", frappe.ui.notifications.total ? false : true);

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
				count: count > 20 ? '20+' : count,
				data_doctype: doctype
			});

		frappe.ui.notifications.dropdown_notification.append($(notification_row));

		frappe.ui.notifications.total += count;
	}
}

// default notification config
frappe.ui.notifications.config = {
	"ToDo": { label: __("To Do") },
	"Chat": { label: __("Chat"), route: "chat"},
	"Event": { label: __("Calendar"), route: "List/Event/Calendar" },
	"Email": { label: __("Email"), route: "List/Communication/Inbox" },
	"Likes": {
		label: __("Likes"),
		click: function() {
			frappe.route_options = {
				show_likes: true
			};

			if (frappe.get_route()[0]=="activity") {
				frappe.pages['activity'].page.list.refresh();
			} else {
				frappe.set_route("activity");
			}
		}
	},
};

frappe.views.show_open_count_list = function(element) {
	var doctype = $(element).attr("data-doctype");
	var filters = frappe.ui.notifications.get_filters(doctype);

	if(filters) {
		frappe.route_options = filters;
	}

	var route = frappe.get_route();
	if(route[0]==="List" && route[1]===doctype) {
		frappe.pages["List/" + doctype].list_view.refresh();
	} else {
		frappe.set_route("List", doctype);
	}
}

frappe.ui.notifications.get_filters = function(doctype) {
	var conditions = frappe.boot.notification_info.conditions[doctype];

	if(conditions && $.isPlainObject(conditions)) {
		return conditions;
	}
}
