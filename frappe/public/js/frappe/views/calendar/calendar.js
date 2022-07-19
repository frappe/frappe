// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.calendar");
frappe.provide("frappe.views.calendars");

frappe.views.CalendarView = class CalendarView extends frappe.views.ListView {

	toggle_result_area() {}

	get view_name() {
		return 'Calendar';
	}

	get_settings() {
		return {
			...super.get_settings(),
			calendar: frappe.views.calendar[this.doctype]
		}
	}

	setup_defaults() {
		super.setup_defaults()
		this.page_title = __('{0} Calendar', [this.page_title]);
		this.calendar_name = frappe.get_route()[3] || "default";
	}

	get_default_args() {
		return {
			...super.get_default_args(),
			calendarWeekends: true,
			calendarView: 'month',
			calendarOffset: 0
		}
	}

	get_route_options_args() {
		let options = super.get_route_options_args();
		const calendar = frappe.route_options.calendar
		if (calendar) {
			options = {
				...options,
				calendarWeekends: Boolean(calendar.weekends),
				calendarView: calendar.view,
				calendarOffset: calendar.offset
			}
		}
		return options
	}

	resolve_route_options() {
		return {
			...super.resolve_route_options(),
			calendar: {
				weekends: this.calendarWeekends,
				view: this.calendarView,
				offset: this.calendarOffset,
			}
		}
	}

	setup_page() {
		this.hide_page_form = true;
		super.setup_page();
	}

	on_change_calendar_weekends(value) {
		this.calendarWeekends = value;
		this.update_route_options();
	}

	on_change_calendar_view(type, offset) {
		this.calendarView = type;
		this.calendarOffset = offset;
		this.update_route_options();
	}

	setup_view() {

	}

	toggle_side_bar() {
		super.toggle_side_bar();
		// refresh calendar when sidebar is toggled to accomodate extra space
		this.render(true);
	}

	render() {
		if (this.calendar === undefined) {
			this.calendar = new frappe.views.Calendar(this.calendar_options);
		} else {
			this.calendar.refresh();
		}
	}

	async init() {
		await super.init()
		this.calendar_options = await this.get_calendar_options();
	}

	async get_calendar_options() {
		const options = {
			doctype: this.doctype,
			parent: this.$result,
			page: this.page,
			list_view: this,
			on_change_view: this.on_change_calendar_view.bind(this),
			on_change_weekends: this.on_change_calendar_weekends.bind(this),
			weekends: this.calendarWeekends,
			defaultView: this.calendarView,
			offset: this.calendarOffset
		};

		return await new Promise(resolve => {
			if (this.calendar_name === 'default') {
				Object.assign(options, this.settings.calendar);
				resolve(options);
			} else {
				frappe.model.with_doc('Calendar View', this.calendar_name, () => {
					const doc = frappe.get_doc('Calendar View', this.calendar_name);
					if (!doc) {
						frappe.show_alert(__("{0} is not a valid Calendar. Redirecting to default Calendar.", [this.calendar_name.bold()]));
						frappe.set_route("List", this.doctype, "Calendar", "default");
						return;
					}
					Object.assign(options, {
						field_map: {
							id: "name",
							start: doc.start_date_field,
							end: doc.end_date_field,
							title: doc.subject_field,
							allDay: doc.all_day ? 1 : 0
						}
					});
					resolve(options);
				});
			}
		});
	}

	get required_libs() {
		let assets = [
			'assets/frappe/js/lib/fullcalendar/fullcalendar.min.css',
			'assets/frappe/js/lib/fullcalendar/fullcalendar.min.js',
		];
		let user_language = frappe.boot.user.language;
		if (user_language && user_language !== 'en') {
			assets.push('assets/frappe/js/lib/fullcalendar/locale-all.js');
		}
		return assets;
	}
};

frappe.views.Calendar = class Calendar {
	constructor(options) {
		$.extend(this, options);
		this.field_map = this.field_map || {
			"id": "name",
			"start": "start",
			"end": "end",
			"allDay": "all_day",
		}
		this.color_map = {
			"danger": "red",
			"success": "green",
			"warning": "orange",
			"default": "blue"
		}
		this.make_page();
		this.setup_options();
		this.make();
		this.setup_view_mode_button();
		this.bind();
	}
	make_page() {
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
		});
	}

	make() {
		this.$wrapper = this.parent;
		this.$cal = $("<div>").appendTo(this.$wrapper);
		this.footnote_area = frappe.utils.set_footnote(this.footnote_area, this.$wrapper,
			__("Select or drag across time slots to create a new event."));
		this.footnote_area.css({"border-top": "0px"});

		this.$cal.fullCalendar(this.cal_options);
		this.set_css();
	}
	setup_view_mode_button() {
		const me = this;
		$(me.footnote_area).find('.btn-weekend').detach();
		let btnTitle = (this.weekends) ? __('Hide Weekends') : __('Show Weekends');
		const btn = `<button class="btn btn-default btn-xs btn-weekend">${btnTitle}</button>`;
		me.footnote_area.append(btn);
	}
	bind() {
		const me = this;
		me.$wrapper.on("click", ".btn-weekend", function() {
			me.weekends = !me.weekends;
			me.$cal.fullCalendar('option', 'weekends', me.weekends);
			me.set_css();
			me.setup_view_mode_button();
			if (me.on_change_weekends !== undefined) {
				me.on_change_weekends(me.weekends);
			}
		});
	}
	set_css() {
		// flatify buttons
		this.$wrapper.find("button.fc-state-default")
			.removeClass("fc-state-default")
			.addClass("btn btn-default");

		this.$wrapper
			.find('.fc-month-button, .fc-agendaWeek-button, .fc-agendaDay-button')
			.wrapAll('<div class="btn-group" />');

		this.$wrapper.find('.fc-prev-button span')
			.attr('class', '').html(frappe.utils.icon('left'));
		this.$wrapper.find('.fc-next-button span')
			.attr('class', '').html(frappe.utils.icon('right'));

		this.$wrapper.find('.fc-today-button')
			.prepend(frappe.utils.icon('today'));

		this.$wrapper.find('.fc-day-number').wrap('<div class="fc-day"></div>');

		var btn_group = this.$wrapper.find(".fc-button-group");
		btn_group.find(".fc-state-active").addClass("active");

		btn_group.find(".btn").on("click", function() {
			btn_group.find(".btn").removeClass("active");
			$(this).addClass("active");
		});
	}
	get_system_datetime(date) {
		date._offset = (moment(date).tz(frappe.sys_defaults.time_zone)._offset);
		return frappe.datetime.convert_to_system_tz(date);
	}
	get_view_span(view) {
		if(view === 'month') {
			return 'months'
		} else if(view === 'agendaWeek') {
			return 'weeks'
		} else if(view === 'agendaDay') {
			return 'days'
		}

		return null;
	}
	setup_options() {
		var me = this;
		const span = this.get_view_span(this.defaultView);
		this.cal_options = {
			meridiem: false,
			locale: frappe.boot.user.language || "en",
			header: {
				left: 'prev, title, next',
				right: 'today, month, agendaWeek, agendaDay'
			},
			editable: true,
			selectable: true,
			selectHelper: true,
			forceEventDuration: true,
			displayEventTime: true,
			defaultView: this.defaultView,
			defaultDate: span ? moment().add(this.offset, span) : moment(),
			weekends: this.weekends,
			nowIndicator: true,
			events: function(start, end, timezone, callback) {
				return frappe.call({
					method: me.get_events_method || "frappe.desk.calendar.get_events",
					type: "GET",
					args: me.get_args(start, end),
					callback: function(r) {
						var events = r.message || [];
						events = me.prepare_events(events);
						callback(events);
					}
				});
			},
			displayEventEnd: true,
			viewRender: function(view) {
				if (me.on_change_view !== undefined) {
					const span = me.get_view_span(view.type)
					me.on_change_view(view.type, span ? view.start.diff(moment(), span) : 0 );
				}
			},
			eventRender: function(event, element) {
				element.attr('title', event.tooltip);
			},
			eventClick: function(event) {
				// edit event description or delete
				var doctype = event.doctype || me.doctype;
				if(frappe.model.can_read(doctype)) {
					frappe.set_route("Form", doctype, event.name);
				}
			},
			eventDrop: function(event, delta, revertFunc) {
				me.update_event(event, revertFunc);
			},
			eventResize: function(event, delta, revertFunc) {
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
	}
	get_args(start, end) {
		var args = {
			doctype: this.doctype,
			start: this.get_system_datetime(start),
			end: this.get_system_datetime(end),
			fields: this.fields,
			filters: this.list_view.filter_area.get(),
			field_map: this.field_map
		};
		return args;
	}
	refresh() {
		this.$cal.fullCalendar('refetchEvents');
	}
	prepare_events(events) {
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

			// show event on single day if start or end date is invalid
			if (!frappe.datetime.validate(d.start) && d.end) {
				d.start = frappe.datetime.add_days(d.end, -1);
			}

			if (d.start && !frappe.datetime.validate(d.end)) {
				d.end = frappe.datetime.add_days(d.start, 1);
			}

			me.fix_end_date_for_event_render(d);
			me.prepare_colors(d);

			d.title = frappe.utils.html2text(d.title);

			return d;
		});
	}
	prepare_colors(d) {
		let color, color_name;
		if(this.get_css_class) {
			color_name = this.color_map[this.get_css_class(d)] || 'blue';

			if (color_name.startsWith("#")) {
				color_name = frappe.ui.color.validate_hex(color_name) ?
					color_name : 'blue';
			}

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
	}
	update_event(event, revertFunc) {
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
	}
	get_update_args(event) {
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
	}

	fix_end_date_for_event_render(event) {
		if (event.allDay) {
			// We use inclusive end dates. This workaround fixes the rendering of events
			event.start = event.start ? $.fullCalendar.moment(event.start).stripTime() : null;
			event.end = event.end ? $.fullCalendar.moment(event.end).add(1, "day").stripTime() : null;
		}
	}
};
