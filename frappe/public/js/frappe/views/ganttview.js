// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.calendar");

frappe.views.GanttFactory = frappe.views.Factory.extend({
	make: function(route) {
		var me = this;

		frappe.require('assets/frappe/js/lib/jQuery.Gantt/css/style.css');
		frappe.require('assets/frappe/js/lib/jQuery.Gantt/js/jquery.fn.gantt.js');

		frappe.model.with_doctype(route[1], function() {
			var page = me.make_page();
			$(page).on("show", function() {
				page.ganttview.set_filters_from_route_options();
			});

			var options = {
				doctype: route[1],
				parent: page
			};
			$.extend(options, frappe.views.calendar[route[1]] || {});

			page.ganttview = new frappe.views.Gantt(options);
		});
	}
});

frappe.views.Gantt = frappe.views.CalendarBase.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make_page();
		frappe.route_options ?
			this.set_filters_from_route_options() :
			this.refresh();
	},
	make_page: function() {
		var module = locals.DocType[this.doctype].module,
			me = this;

		this.page = this.parent.page;
		this.page.set_title(__("Gantt Chart") + " - " + __(this.doctype));
		frappe.breadcrumbs.add(module, this.doctype);

		this.page.set_secondary_action(__("Refresh"),
			function() { me.refresh(); }, "icon-refresh")

		this.page.add_field({fieldtype:"Date", label:"From",
			fieldname:"start", "default": frappe.datetime.month_start(), input_css: {"z-index": 3}});

		this.page.add_field({fieldtype:"Date", label:"To",
			fieldname:"end", "default": frappe.datetime.month_end(), input_css: {"z-index": 3}});

		this.add_filters();
		this.wrapper = $("<div style='position:relative;z-index:1;'></div>").appendTo(this.page.main);

	},
	refresh: function() {
		var me = this;
		return frappe.call({
			method: this.get_events_method,
			type: "GET",
			args: {
				doctype: this.doctype,
				start: this.page.fields_dict.start.get_parsed_value(),
				end: this.page.fields_dict.end.get_parsed_value(),
				filters: this.get_filters()
			},
			callback: function(r) {
				$(me.wrapper).empty();
				if(!r.message || !r.message.length) {
					$(me.wrapper).html('<p class="text-muted" style="padding: 15px;">' + __('Nothing to show for this selection') + '</p>');
				} else {
					var gantt_area = $('<div class="gantt">').appendTo(me.wrapper);
					gantt_area.gantt({
						source: me.get_source(r),
						navigate: "scroll",
						scale: "days",
						minScale: "hours",
						maxScale: "months",
						itemsPerPage: 20,
						onItemClick: function(data) {
							frappe.set_route('Form', me.doctype, data.name);
						},
						onAddClick: function(dt, rowId) {
							newdoc(me.doctype);
						}
					});
				}
			}
		})

	},
	get_source: function(r) {
		var source = [],
			me = this;
		// projects
		$.each(r.message, function(i,v) {

			// standardize values
			$.each(me.field_map, function(target, source) {
				v[target] = v[source];
			});

			if(v.start && !v.end) {
				v.end = new Date(v.start)
				v.end.setHours(v.end.getHours() + 1);
			}

			if(v.start && v.end) {
				source.push({
					name: v.title,
					desc: v.status,
					values: [{
						name: v.title,
						desc: v.title + "<br>" + (v.status || ""),
						from: '/Date('+moment(v.start).format("X")+'000)/',
						to: '/Date('+moment(v.end).format("X")+'000)/',
						customClass: {
							'danger':'ganttRed',
							'warning':'ganttOrange',
							'info':'ganttBlue',
							'success':'ganttGreen',
							'':'ganttGray'
						}[me.style_map ?
							me.style_map[v.status] :
							frappe.utils.guess_style(v.status, "standard")],
						dataObj: v
					}]
				})
			}
		});
		return source
	}
});
