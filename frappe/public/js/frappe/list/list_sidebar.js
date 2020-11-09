// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide('frappe.views');

// opts:
// stats = list of fields
// doctype
// parent
// set_filter = function called on click

frappe.views.ListSidebar = class ListSidebar {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		var sidebar_content = frappe.render_template("list_sidebar", { doctype: this.doctype });

		this.sidebar = $('<div class="list-sidebar overlay-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.setup_list_group_by();

		// do not remove
		// used to trigger custom scripts
		$(document).trigger('list_sidebar_setup');

		if (this.list_view.list_view_settings && this.list_view.list_view_settings.disable_sidebar_stats) {
			this.sidebar.find('.sidebar-stat').remove();
		} else {
			this.sidebar.find('.list-stats').on('click', (e) => {
				this.reload_stats();
			});
		}

	}

	setup_list_group_by() {
		this.list_group_by = new frappe.views.ListGroupBy({
			doctype: this.doctype,
			sidebar: this,
			list_view: this.list_view,
			page: this.page
		});
	}

	get_stats() {
		var me = this;
		frappe.call({
			method: 'frappe.desk.reportview.get_sidebar_stats',
			type: 'GET',
			args: {
				stats: me.stats,
				doctype: me.doctype,
				// wait for list filter area to be generated before getting filters, or fallback to default filters
				filters: (me.list_view.filter_area ? me.list_view.get_filters_for_args() : me.default_filters) || []
			},
			callback: function(r) {
				me.render_stat((r.message.stats || {})["_user_tags"]);
				let stats_dropdown = me.sidebar.find('.list-stats-dropdown');
				frappe.utils.setup_search(stats_dropdown, '.stat-link', '.stat-label');
			}
		});
	}

	render_stat(stats) {
		let args = {
			stats: stats,
			label: __("Tags")
		};

		let tag_list = $(frappe.render_template("list_sidebar_stat", args)).on("click", ".stat-link", (e) => {
			let fieldname = $(e.currentTarget).attr('data-field');
			let label = $(e.currentTarget).attr('data-label');
			let condition = "like";
			let existing = this.list_view.filter_area.filter_list.get_filter(fieldname);
			if (existing) {
				existing.remove();
			}
			if (label == "No Tags") {
				label = "%,%";
				condition = "not like";
			}
			this.list_view.filter_area.add(
				this.doctype,
				fieldname,
				condition,
				label
			);
		});

		this.sidebar.find(".list-stats-dropdown .stat-result").html(tag_list);
	}

	reload_stats() {
		this.sidebar.find(".stat-link").remove();
		this.sidebar.find(".stat-no-records").remove();
		this.get_stats();
	}
};
