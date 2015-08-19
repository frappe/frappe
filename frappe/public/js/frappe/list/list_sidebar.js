// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views');

// opts:
// stats = list of fields
// doctype
// parent
// set_filter = function called on click

frappe.views.ListSidebar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.get_stats();
	},
	make: function() {
		var sidebar_content = frappe.render_template("list_sidebar", {doctype: this.doclistview.doctype});

		this.offcanvas_list_sidebar = $(".offcanvas .list-sidebar").html(sidebar_content);
		this.page_sidebar = $('<div class="list-sidebar hidden-xs hidden-sm"></div>')
			.html(sidebar_content)
			.appendTo(this.page.sidebar.empty());

		this.sidebar = this.page_sidebar.add(this.offcanvas_list_sidebar);

		this.setup_assigned_to_me();

		if(frappe.views.calendar[this.doctype]) {
			this.sidebar.find(".calendar-link, .gantt-link").removeClass("hide");
		}
	},
	setup_assigned_to_me: function() {
		var me = this;
		this.page.sidebar.find(".assigned-to-me a").on("click", function() {
			me.doclistview.assigned_to_me();
		});

		this.offcanvas_list_sidebar.find(".assigned-to-me a").on("click", function() {
			me.doclistview.assigned_to_me();
		});
	},
	get_stats: function() {
		var me = this
		return frappe.call({
			type: "GET",
			method: 'frappe.desk.reportview.get_stats',
			args: {
				stats: me.stats,
				doctype: me.doctype
			},
			callback: function(r) {
				// This gives a predictable stats order
				$.each(me.stats, function(i, v) {
					me.render_stat(v, (r.message || {})[v]);
				});

				// reload button at the end
				// if(me.stats.length) {
				// 	$('<a class="small text-muted">'+__('Refresh Stats')+'</a>')
				// 		.css({"margin-top":"15px", "display":"inline-block"})
				// 		.click(function() {
				// 			me.reload_stats();
				// 			return false;
				// 		}).appendTo($('<div class="stat-wrapper">')
				// 			.appendTo(me.sidebar));
				// }

				me.doclistview.set_sidebar_height();
			}
		});
	},
	render_stat: function(field, stat) {
		var me = this;
		var sum = 0;
		var label = frappe.meta.docfield_map[this.doctype][field] ?
			frappe.meta.docfield_map[this.doctype][field].label : field;
		var show_tags = '<a class="list-tag-preview hidden-xs" title="' + __("Show tags")
			+ '"><i class="octicon octicon-pencil"></i></a>';

		stat = (stat || []).sort(function(a, b) { return b[1] - a[1] });
		$.each(stat, function(i,v) { sum = sum + v[1]; })

		var context = {
			field: field,
			stat: stat,
			sum: sum,
			label: label==='_user_tags' ? (__("Tags") + show_tags) : __(label),
		};

		var sidebar_stat = $(frappe.render_template("list_sidebar_stat", context))
			.on("click", ".stat-link", function() {
				var fieldname = $(this).attr('data-field');
				var label = $(this).attr('data-label');
				me.set_filter(fieldname, label);
				return false;
			})
			.appendTo(this.sidebar);
	},
	reload_stats: function() {
		this.sidebar.find(".sidebar-stat").remove();
		this.get_stats();
	},
});
