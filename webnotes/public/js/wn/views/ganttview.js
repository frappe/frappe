// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide("wn.views.calendar");

wn.views.GanttFactory = wn.views.Factory.extend({
	make: function(route) {
		var me = this;
		wn.model.with_doctype(route[1], function() {
			var page = me.make_page();
			$(page).on("show", function() {
				me.set_filters_from_route_options();
			});
			
			var options = {
				doctype: route[1],
				page: page
			};
			$.extend(options, wn.views.calendar[route[1]] || {});

			page.ganttview = new wn.views.Gantt(options);
		});
	}
});

wn.views.Gantt = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		wn.require('assets/webnotes/js/lib/jQuery.Gantt/css/style.css');
		wn.require('assets/webnotes/js/lib/jQuery.Gantt/js/jquery.fn.gantt.js');
		
		this.make_page();
		wn.route_options ?
			this.set_filters_from_route_options() :
			this.refresh();
	},
	make_page: function() {
		var module = locals.DocType[this.doctype].module,
			me = this;
			
		this.appframe = this.page.appframe;
		this.appframe.set_title(wn._("Gantt Chart") + " - " + wn._(this.doctype));
		this.appframe.add_module_icon(module)
		this.appframe.set_views_for(this.doctype, "gantt");

		this.appframe.set_title_right("Refresh", 
			function() { me.refresh(); }, "icon-refresh")

		this.appframe.add_field({fieldtype:"Date", label:"From", 
			fieldname:"start", "default": wn.datetime.month_start(), input_css: {"z-index": 3}});

		this.appframe.add_field({fieldtype:"Date", label:"To", 
			fieldname:"end", "default": wn.datetime.month_end(), input_css: {"z-index": 3}});
			
		if(this.filters) {
			$.each(this.filters, function(i, df) {
				me.appframe.add_field(df);
				return false;
			});
		}
	},
	refresh: function() {
		var parent = $(this.page)
			.find(".layout-main")
			.empty()
			.css('min-height', '300px')
			.html('<div class="alert alert-info">Loading...</div>');
		
		var me = this;
		return wn.call({
			method: this.get_events_method,
			type: "GET",
			args: {
				doctype: this.doctype,
				start: this.appframe.fields_dict.start.get_parsed_value(),
				end: this.appframe.fields_dict.end.get_parsed_value(),
				filters: this.get_filters()
			},
			callback: function(r) {
				$(parent).empty();
				if(!r.message || !r.message.length) {
					$(parent).html('<div class="alert alert-info">' + wn._('Nothing to show for this selection') + '</div>');
				} else {
					var gantt_area = $('<div class="gantt">').appendTo(parent);
					gantt_area.gantt({
						source: me.get_source(r),
						navigate: "scroll",
						scale: "days",
						minScale: "hours",
						maxScale: "months",
						onItemClick: function(data) {
							wn.set_route('Form', me.doctype, data.name);
						},
						onAddClick: function(dt, rowId) {
							newdoc(me.doctype);
						}
					});				
				}
			}
		})
		
	},
	set_filter: function(doctype, value) {
		var me = this;
		if(this.filters) {
			$.each(this.filters, function(i, df) {
				if(df.options===value)
					me.appframe.fields_dict[df.fieldname].set_input(value);
					return false;
			});
		}
	},
	get_filters: function() {
		var filter_vals = {},
			me = this;
		if(this.filters) {
			$.each(this.filters, function(i, df) {
				filter_vals[df.fieldname || df.label] = 
					me.appframe.fields_dict[df.fieldname || df.label].get_parsed_value();
			});
		}
		return filter_vals;
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
						desc: v.title + "<br>" + v.status,
						from: '/Date("'+v.start+'")/',
						to: '/Date("'+v.end+'")/',
						customClass: {
							'danger':'ganttRed',
							'warning':'ganttOrange',
							'info':'ganttBlue',
							'success':'ganttGreen',
							'':'ganttGray'
						}[me.style_map ? 
							me.style_map[v.status] :
							wn.utils.guess_style(v.status, "standard")],
						dataObj: v
					}]
				})				
			}
		});
		return source	
	},
	set_filters_from_route_options: function() {
		var me = this;
		if(wn.route_options) {
			$.each(wn.route_options, function(k, value) {
				if(me.appframe.fields_dict[k]) {
					me.appframe.fields_dict[k].set_input(value);
					me.refresh();
					return false;
				};
			})
			wn.route_options = null;
		}
	}
});
