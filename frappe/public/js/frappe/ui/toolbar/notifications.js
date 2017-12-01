frappe.provide("frappe.ui.notifications");

frappe.ui.notifications = {
	config: {
		"ToDo": { label: __("To Do") },
		"Chat": { label: __("Chat"), route: "chat"},
		"Event": { label: __("Calendar"), route: "List/Event/Calendar" },
		"Email": { label: __("Email"), route: "List/Communication/Inbox" },
		"Likes": { label: __("Likes"),
			click: function() {
				frappe.route_options = { show_likes: true };
				if (frappe.get_route()[0]=="activity") {
					frappe.pages['activity'].page.list.refresh();
				} else {
					frappe.set_route("activity");
				}
			}
		},
	},

	update_notifications: function() {
		this.total = 0;
		this.dropdown = $("#dropdown-notification").empty();
		this.boot_info = frappe.boot.notification_info;
		let defaults = ["Comment", "ToDo", "Event"];

		this.get_counts(this.boot_info.open_count_doctype, 1, defaults);
		this.get_counts(this.boot_info.open_count_other, 1);

		// Target counts are stored for docs per doctype
		let targets = { doctypes : {} }, map = this.boot_info.targets;
		Object.keys(map).map(doctype => {
			Object.keys(map[doctype]).map(doc => {
				targets[doc] = map[doctype][doc];
				targets.doctypes[doc] = doctype;
			});
		});
		this.get_counts(targets, 1, null, ["doctypes"], true);
		this.get_counts(this.boot_info.open_count_doctype,
			0, null, defaults);

		this.bind_list();

		// switch colour on the navbar and disable if no notifications
		$(".navbar-new-comments")
			.html(this.total > 99 ? '99+' : this.total)
			.toggleClass("navbar-new-comments-true", this.total ? true : false)
			.parent().toggleClass("disabled", this.total ? false : true);
	},

	get_counts: function(map, divide, keys, excluded = [], target = false) {
		let empty_map = 1;
		keys = keys ? keys
			: Object.keys(map).sort().filter(e => !excluded.includes(e));
		keys.map(key => {
			let doc_dt = (map.doctypes) ? map.doctypes[key] : undefined;
			if(map[key] > 0 || target) {
				this.add_notification(key, map[key], doc_dt, target);
				empty_map = 0;
			}
		});
		if(divide && !empty_map) {
			this.dropdown.append($('<li class="divider"></li>'));
		}
	},

	add_notification: function(name, value, doc_dt, target = false) {
		let label = this.config[name] ? this.config[name].label : name;
		let $list_item = !target
			? $(`<li><a class="badge-hover" data-doctype="${name}">${__(label)}
				<span class="badge pull-right">${value}</span>
			</a></li>`)
			: $(`<li><a class="progress-small" data-doctype="${doc_dt}"
				data-doc="${name}"><span class="dropdown-item-label">${__(label)}<span>
				<div class="progress-chart"><div class="progress">
					<div class="progress-bar" style="width: ${value}%"></div>
				</div></div>
			</a></li>`);
		this.dropdown.append($list_item);
		if(!target) this.total += value;
	},

	bind_list: function() {
		var me = this;
		$("#dropdown-notification a").on("click", function() {
			var doctype = $(this).attr("data-doctype");
			var doc = $(this).attr("data-doc");
			if(!doc) {
				var config = me.config[doctype] || {};
				if (config.route) {
					frappe.set_route(config.route);
				} else if (config.click) {
					config.click();
				} else {
					frappe.ui.notifications.show_open_count_list(doctype);
				}
			} else {
				frappe.set_route("Form", doctype, doc);
			}
		});
	},

	show_open_count_list: function(doctype) {
		let filters = this.boot_info.conditions[doctype];
		if(filters && $.isPlainObject(filters)) {
			if (!frappe.route_options) {
				frappe.route_options = {};
			}
			$.extend(frappe.route_options, filters);
		}
		let route = frappe.get_route();
		if(route[0]==="List" && route[1]===doctype) {
			frappe.pages["List/" + doctype].list_view.refresh();
		} else {
			frappe.set_route("List", doctype);
		}
	},
}