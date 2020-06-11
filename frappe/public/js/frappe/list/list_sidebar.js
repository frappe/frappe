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
		this.cat_tags = [];
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

	get_cat_tags() {
		return this.cat_tags;
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
				me.render_stat("_user_tags", (r.message.stats || {})["_user_tags"]);
				let stats_dropdown = me.sidebar.find('.list-stats-dropdown');
				frappe.utils.setup_search(stats_dropdown, '.stat-link', '.stat-label');
			}
		});
	}

	render_stat(field, stat, tags) {
		var me = this;
		var sum = 0;
		var stats = [];
		var label = frappe.meta.docfield_map[this.doctype][field] ?
			frappe.meta.docfield_map[this.doctype][field].label : field;

		stat = (stat || []).sort(function(a, b) {
			return b[1] - a[1];
		});
		$.each(stat, function(i, v) {
			sum = sum + v[1];
		});

		if (tags) {
			for (var t in tags) {
				var nfound = -1;
				for (var i in stat) {
					if (tags[t] === stat[i][0]) {
						stats.push(stat[i]);
						nfound = i;
						break;
					}
				}
				if (nfound < 0) {
					stats.push([tags[t], 0]);
				} else {
					me.tempstats["_user_tags"].splice(nfound, 1);
				}
			}
			field = "_user_tags";
		} else {
			stats = stat;
		}
		var context = {
			field: field,
			stat: stats,
			sum: sum,
			label: field === '_user_tags' ? (tags ? __(label) : __("Tags")) : __(label),
		};
		$(frappe.render_template("list_sidebar_stat", context))
			.on("click", ".stat-link", function() {
				var fieldname = $(this).attr('data-field');
				var label = $(this).attr('data-label');
				var condition = "like";
				var existing = me.list_view.filter_area.filter_list.get_filter(fieldname);
				if(existing) {
					existing.remove();
				}
				if (label == "No Tags") {
					label = "%,%";
					condition = "not like";
				}
				me.list_view.filter_area.filter_list.add_filter(me.list_view.doctype, fieldname, condition, label)
					.then(function() {
						me.list_view.refresh();
					});
			})
			.appendTo(this.sidebar.find(".list-stats-dropdown"));
	}

	set_fieldtype(df) {

		// scrub
		if (df.fieldname == "docstatus") {
			df.fieldtype = "Select",
			df.options = [
				{ value: 0, label: "Draft" },
				{ value: 1, label: "Submitted" },
				{ value: 2, label: "Cancelled" },
			];
		} else if (df.fieldtype == 'Check') {
			df.fieldtype = 'Select';
			df.options = [{ value: 0, label: 'No' },
				{ value: 1, label: 'Yes' }
			];
		} else if (['Text', 'Small Text', 'Text Editor', 'Code', 'Tag', 'Comments',
			'Dynamic Link', 'Read Only', 'Assign'
		].indexOf(df.fieldtype) != -1) {
			df.fieldtype = 'Data';
		} else if (df.fieldtype == 'Link' && this.$w.find('.condition').val() != "=") {
			df.fieldtype = 'Data';
		}
		if (df.fieldtype === "Data" && (df.options || "").toLowerCase() === "email") {
			df.options = null;
		}
	}

	reload_stats() {
		this.sidebar.find(".stat-link").remove();
		this.sidebar.find(".stat-no-records").remove();
		this.get_stats();
	}

	get_divider() {
		return $('<li role="separator" class="divider"></li>');
	}
};
