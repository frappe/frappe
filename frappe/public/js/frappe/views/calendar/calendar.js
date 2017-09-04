// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.calendar");
frappe.provide("frappe.views.calendars");

frappe.views.CalendarView = frappe.views.ListRenderer.extend({
	name: 'Calendar',
	render_view: function() {
		var me = this;
		var options = {
			doctype: this.doctype,
			parent: this.wrapper,
			page: this.list_view.page,
			list_view: this.list_view
		}
		$.extend(options, frappe.views.calendar[this.doctype]);
		this.calendar = new frappe.views.Calendar(options);
	},
	set_defaults: function() {
		this._super();
		this.page_title = this.page_title + ' ' + __('Calendar');
		this.no_realtime = true;
		this.show_no_result = false;
		this.hide_sort_selector = true;
	},
	get_header_html: function() {
		return null;
	},
	required_libs: [
		'assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
		'assets/frappe/js/lib/fullcalendar/fullcalendar.min.js',
		'assets/frappe/js/lib/fullcalendar/locale-all.js'
	]
})

frappe.views.Calendar = Class.extend({
	init: function(options) {
		$.extend(this, options);
		this.make_page();
		this.setup_options();
		this.make();
	},
	make_page: function() {
		var me = this;

		// add links to other calendars
		me.page.clear_user_actions();
		$.each(frappe.boot.calendars, function(i, doctype) {
			if(frappe.model.can_read(doctype)) {
				me.page.add_menu_item(__(doctype), function() {
					frappe.set_route("List", doctype, "Calendar");
				});
			}
		});

		$(this.parent).on("show", function() {
			me.$cal.fullCalendar("refetchEvents");
		})
	},

	make: function() {
		var me = this;
		this.$wrapper = this.parent;
		this.$cal = $("<div>").appendTo(this.$wrapper);
		this.footnote_area = frappe.utils.set_footnote(this.footnote_area, this.$wrapper,
			__("Select or drag across time slots to create a new event."));
		this.footnote_area.css({"border-top": "0px"});

		this.$cal.fullCalendar(this.cal_options);
		this.set_css();
	},
	set_css: function() {
		// flatify buttons
		this.$wrapper.find("button.fc-state-default")
			.removeClass("fc-state-default")
			.addClass("btn btn-default");

		this.$wrapper.find(".fc-button-group").addClass("btn-group");

		this.$wrapper.find('.fc-prev-button span')
			.attr('class', '').addClass('fa fa-chevron-left')
		this.$wrapper.find('.fc-next-button span')
			.attr('class', '').addClass('fa fa-chevron-right')

		var btn_group = this.$wrapper.find(".fc-button-group");
		btn_group.find(".fc-state-active").addClass("active");

		btn_group.find(".btn").on("click", function() {
			btn_group.find(".btn").removeClass("active");
			$(this).addClass("active");
		});
	},
	field_map: {
		"id": "name",
		"start": "start",
		"end": "end",
		"allDay": "all_day",
	},
	color_map: {
		"danger": "red",
		"success": "green",
		"warning": "orange",
		"default": "blue"
	},
	get_system_datetime: function(date) {
		date._offset = moment.user_utc_offset;
		return frappe.datetime.convert_to_system_tz(date);
	},
	setup_options: function() {
		var me = this;
		this.cal_options = {
			locale: frappe.boot.user.language || "en",
			header: {
				left: 'title',
				center: '',
				right: 'prev,next month,agendaWeek,agendaDay'
			},
			editable: true,
			selectable: true,
			selectHelper: true,
			forceEventDuration: true,
			events: function(start, end, timezone, callback) {
				return frappe.call({
					method: me.get_events_method || "frappe.desk.calendar.get_events",
					type: "GET",
					args: me.get_args(start, end),
					callback: function(r) {
						var events = r.message;
						events = me.prepare_events(events);
						callback(events);
					}
				})
			},
			eventRender: function(event, element) {
				element.attr('title', event.tooltip);
			},
			eventClick: function(event, jsEvent, view) {
				// edit event description or delete
				var doctype = event.doctype || me.doctype;
				if(frappe.model.can_read(doctype)) {
					frappe.set_route("Form", doctype, event.name);
				}
			},
			eventDrop: function(event, delta, revertFunc, jsEvent, ui, view) {
				me.update_event(event, revertFunc);
			},
			eventResize: function(event, delta, revertFunc, jsEvent, ui, view) {
				me.update_event(event, revertFunc);
			},
			select: function(startDate, endDate, jsEvent, view) {
				if (view.name==="month" && (endDate - startDate)===86400000) {
					// detect single day click in month view
					return;
				}

				var event = frappe.model.get_new_doc(me.doctype);

				event[me.field_map.start] = me.get_system_datetime(startDate);

				if(me.field_map.end)
					event[me.field_map.end] = me.get_system_datetime(endDate);

				if(me.field_map.allDay) {
					var all_day = (startDate._ambigTime && endDate._ambigTime) ? 1 : 0;

					event[me.field_map.allDay] = all_day;

					if (all_day)
						event[me.field_map.end] = me.get_system_datetime(moment(endDate).subtract(1, "s"));
				}

				frappe.set_route("Form", me.doctype, event.name);
			},
			dayClick: function(date, jsEvent, view) {
				if(view.name === 'month') {
					const $date_cell = $('td[data-date=' + date.format('YYYY-MM-DD') + "]");

					if($date_cell.hasClass('date-clicked')) {
						me.$cal.fullCalendar('changeView', 'agendaDay');
						me.$cal.fullCalendar('gotoDate', date);
						me.$wrapper.find('.date-clicked').removeClass('date-clicked');

						// update "active view" btn
						me.$wrapper.find('.fc-month-button').removeClass('active');
						me.$wrapper.find('.fc-agendaDay-button').addClass('active');
					}

					me.$wrapper.find('.date-clicked').removeClass('date-clicked');
					$date_cell.addClass('date-clicked');
				}
				return false;
			}
		};

		if(this.options) {
			$.extend(this.cal_options, this.options);
		}
	},
	get_args: function(start, end) {
		var args = {
			doctype: this.doctype,
			start: this.get_system_datetime(start),
			end: this.get_system_datetime(end),
			filters: this.list_view.filter_list.get_filters()
		};
		return args;
	},
	refresh: function() {
		this.$cal.fullCalendar('refetchEvents');
	},
	prepare_events: function(events) {
		var me = this;

		return (events || []).map(d => {
			d.id = d.name;
			d.editable = frappe.model.can_write(d.doctype || me.doctype);

			// do not allow submitted/cancelled events to be moved / extended
			if(d.docstatus && d.docstatus > 0) {
				d.editable = false;
			}

			$.each(me.field_map, function(target, source) {
				d[target] = d[source];
			});

			if(!me.field_map.allDay)
				d.allDay = 1;

			// convert to user tz
			d.start = frappe.datetime.convert_to_user_tz(d.start);
			d.end = frappe.datetime.convert_to_user_tz(d.end);

			me.fix_end_date_for_event_render(d);
			me.prepare_colors(d);
			return d;
		});
	},
	prepare_colors: function(d) {
		let color, color_name;
		if(this.get_css_class) {
			color_name = this.color_map[this.get_css_class(d)];
			color_name =
				frappe.ui.color.validate_hex(color_name) ?
					color_name :
					'blue';
			d.backgroundColor = frappe.ui.color.get(color_name, 'extra-light');
			d.textColor = frappe.ui.color.get(color_name, 'dark');
		} else {
			color = d.color;
			if (!frappe.ui.color.validate_hex(color) || !color) {
				color = frappe.ui.color.get('blue', 'extra-light');
			}
			d.backgroundColor = color;
			d.textColor = frappe.ui.color.get_contrast_color(color);
		}
		return d;
	},
	update_event: function(event, revertFunc) {
		var me = this;
		frappe.model.remove_from_locals(me.doctype, event.name);
		return frappe.call({
			method: me.update_event_method || "frappe.desk.calendar.update_event",
			args: me.get_update_args(event),
			callback: function(r) {
				if(r.exc) {
					frappe.show_alert(__("Unable to update event"));
					revertFunc();
				}
			},
			error: function() {
				revertFunc();
			}
		});
	},
	get_update_args: function(event) {
		var me = this;
		var args = {
			name: event[this.field_map.id]
		};

		args[this.field_map.start] = me.get_system_datetime(event.start);

		if(this.field_map.allDay)
			args[this.field_map.allDay] = (event.start._ambigTime && event.end._ambigTime) ? 1 : 0;

		if(this.field_map.end) {
			if (!event.end) {
				event.end = event.start.add(1, "hour");
			}

			args[this.field_map.end] = me.get_system_datetime(event.end);

			if (args[this.field_map.allDay]) {
				args[this.field_map.end] = me.get_system_datetime(moment(event.end).subtract(1, "s"));
			}
		}

		args.doctype = event.doctype || this.doctype;

		return { args: args, field_map: this.field_map };
	},

	fix_end_date_for_event_render: function(event) {
		if (event.allDay) {
			// We use inclusive end dates. This workaround fixes the rendering of events
			event.start = event.start ? $.fullCalendar.moment(event.start).stripTime() : null;
			event.end = event.end ? $.fullCalendar.moment(event.end).add(1, "day").stripTime() : null;
		}
	}
})
