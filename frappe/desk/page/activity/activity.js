// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.pages['activity'].onload = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Activity"),
		single_column: true
	})
	frappe.add_breadcrumbs("Activity");

	var list = new frappe.ui.Listing({
		hide_refresh: true,
		appframe: wrapper.appframe,
		method: 'frappe.desk.page.activity.activity.get_feed',
		parent: $(wrapper).find(".layout-main"),
		render_row: function(row, data) {
			new frappe.ActivityFeed(row, data);
		}
	});
	list.run();

	wrapper.appframe.set_title_right(__("Refresh"), function() { list.run(); });

	// Build Report Button
	if(frappe.boot.user.can_get_report.indexOf("Feed")!=-1) {
		wrapper.appframe.add_button(__('Build Report'), function() {
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

		$(row).append(repl('<div style="margin: 0px">\
			<span class="avatar avatar-small">\
				<img src="%(imgsrc)s" /></span> \
			<i class="icon-fixed-width %(icon)s" style="margin-right: 5px;"></i>\
			<a %(onclick)s class="label %(add_class)s">\
				%(feed_type)s</a>\
			<span class="small">%(subject)s</span>\
			<span class="user-info">%(by)s / %(when)s</span></div>', data));
	},
	scrub_data: function(data) {
		data.by = frappe.user_info(data.owner).fullname;
		data.imgsrc = frappe.utils.get_file_link(frappe.user_info(data.owner).image);

		data.icon = "icon-flag";
		if(data.doc_type) {
			data.feed_type = data.doc_type;
			data.onclick = repl('href="#Form/%(doc_type)s/%(doc_name)s"', data);
			data.icon = frappe.boot.doctype_icons[data.doc_type];
		}

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
			$(row).html(repl('<div class="date-sep" style="padding-left: 15px;">%(date)s</div>', {date: pdate}));
		}
		frappe.last_feed_date = date;
	}
})
