wn.provide("wn.views.calendar");

wn.views.GanttFactory = wn.views.Factory.extend({
	make: function(route) {
		var me = this;
		wn.model.with_doctype(route[1], function() {
			var options = {
				doctype: route[1],
				page: me.make_page()
			};
			$.extend(options, wn.views.calendar[route[1]] || {});

			new wn.views.Gantt(options);
		});
	}
});

wn.views.Gantt = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		wn.require('lib/js/lib/jQuery.Gantt/css/style.css');
		wn.require('lib/js/lib/jQuery.Gantt/js/jquery.fn.gantt.js');
		
		this.make_page();
		this.make_chart();
		
	},
	make_page: function() {
		var module = locals.DocType[this.doctype].module;
		this.page.appframe.set_title(wn._("Gantt Chart") + " - " + wn._(this.doctype));
		this.page.appframe.add_module_icon(module)
		this.page.appframe.set_views_for(this.doctype, "gantt");
	},
	make_chart: function() {
		var parent = $(this.page)
			.find(".layout-main")
			.empty()
			.css('min-height', '300px')
			.html('<div class="alert">Loading...</div>');
		
		var me = this;
		wn.call({
			method: this.get_events_method,
			type: "GET",
			args: {
				doctype: this.doctype,
				start: "2013-01-01",
				end: "2014-01-01"
			},
			callback: function(r) {
				$(parent).empty();
				if(!r.message.length) {
					$(parent).html('<div class="alert">No Tasks Yet.</div>');
				} else {
					var gantt_area = $('<div class="gantt">').appendTo(parent);
					gantt_area.gantt({
						source: me.get_source(r),
						navigate: "scroll",
						scale: "weeks",
						minScale: "day",
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
	get_source: function(r) {
		var source = [],
			me = this;
		// projects
		$.each(r.message, function(i,v) {

			// standardize values
			$.each(me.field_map, function(target, source) {
				v[target] = v[source];
			});

			if(v.start && v.end) {
				source.push({
					name: v.project || " ", 
					desc: v.subject,
					values: [{
						name: v.title,
						desc: v.status,
						from: '/Date("'+v.start+'")/',
						to: '/Date("'+v.end+'")/',
						customClass: {
							'danger':'ganttRed',
							'warning':'ganttOrange',
							'info':'ganttBlue',
							'success':'ganttGreen',
							'':'ganttGray'
						}[me.style_map[v.status]],
						dataObj: v
					}]
				})				
			}
		});
		return source	
	}	
});
