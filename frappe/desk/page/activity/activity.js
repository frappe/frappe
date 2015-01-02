// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.pages['activity'].onload = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		single_column: true
	});

	page.set_title(__("Activty"), frappe.get_module("Activity").icon);

	var list = new frappe.ui.Listing({
		hide_refresh: true,
		page: wrapper.page,
		method: 'frappe.desk.page.activity.activity.get_feed',
		parent: $(wrapper).find(".layout-main"),
		render_row: function(row, data) {
			new frappe.ActivityFeed(row, data);
		}
	});
	list.run();

	this.page.main.on("click", ".activity-message", function() {
		var doctype = $(this).attr("data-doctype"),
			docname = $(this).attr("data-docname");
		if (doctype && docname) {
			frappe.set_route(["Form", doctype, docname]);
		}
	});

	wrapper.page.set_primary_action(__("Refresh"), function() { list.run(); });

	// Build Report Button
	if(frappe.boot.user.can_get_report.indexOf("Feed")!=-1) {
		wrapper.page.set_secondary_action(__('Build Report'), function() {
			frappe.set_route('Report', "Feed");
		}, 'icon-th');
	}
}

frappe.last_feed_date = false;
frappe.ActivityFeed = Class.extend({
	init: function(row, data) {
		this.scrub_data(data);
		this.add_date_separator(row, data);
		if(!data.add_class)
			data.add_class = "label-default";

		$(row).append(frappe.render_template("activity_row", data));
	},
	scrub_data: function(data) {
		data.by = frappe.user_info(data.owner).fullname;
		data.imgsrc = frappe.utils.get_file_link(frappe.user_info(data.owner).image);

		data.icon = "icon-flag";
		if(data.doc_type) {
			data.feed_type = data.doc_type;
			data.icon = frappe.boot.doctype_icons[data.doc_type];
		}

		data.feed_type = data.feed_type || "Comment";

		// color for comment
		data.add_class = {
			"Comment": "label-danger",
			"Assignment": "label-warning",
			"Login": "label-default"
		}[data.feed_type] || "label-info"

		data.when = comment_when(data.creation);
		data.feed_type = __(data.feed_type);
	},
	add_date_separator: function(row, data) {
		var date = dateutil.str_to_obj(data.modified);
		var last = frappe.last_feed_date;

		if((last && dateutil.obj_to_str(last) != dateutil.obj_to_str(date)) || (!last)) {
			var diff = dateutil.get_day_diff(dateutil.get_today(), dateutil.obj_to_str(date));
			if(diff < 1) {
				pdate = 'Today';
			} else if(diff < 2) {
				pdate = 'Yesterday';
			} else {
				pdate = dateutil.global_date_format(date);
			}
			data.date_sep = pdate;
			data.date_class = "date-indicator";
		} else {
			data.date_sep = null;
			data.date_class = "";
		}
		frappe.last_feed_date = date;
	}
})
