// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.calendar");
frappe.provide("frappe.views.calendars");

frappe.views.CalendarView = class CalendarView extends frappe.views.ListView {
	static load_last_view() {
		const route = frappe.get_route();
		if (route.length === 3) {
			const doctype = route[1];
			const user_settings = frappe.get_user_settings(doctype)["Calendar"] || {};
			route.push(user_settings.last_calendar || "default");
			frappe.route_flags.replace_route = true;
			frappe.set_route(route);
			return true;
		} else {
			return false;
		}
	}

	toggle_result_area() {}

	get view_name() {
		return "Calendar";
	}

	setup_defaults() {
		return super.setup_defaults().then(() => {
			this.page_title = __("{0} Calendar", [this.page_title]);
			this.calendar_settings = frappe.views.Calendar[this.doctype] || {};
			this.calendar_name = frappe.get_route()[3];
		});
	}

	setup_page() {
		this.hide_page_form = true;
		super.setup_page();
	}

	setup_view() {}

	before_render() {
		super.before_render();
		this.save_view_user_settings({
			last_calendar: this.calendar_name,
		});
	}

	render() {
		if (this.calendar) {
			this.calendar.refresh();
			return;
		}

		this.load_lib
			.then(() => this.get_calendar_preferences())
			.then((options) => {
				this.calendar = new frappe.views.Calendar(options);
			});
	}

	get_calendar_preferences() {
		const options = {
			doctype: this.doctype,
			parent: this.$result,
			page: this.page,
			list_view: this,
		};
		const calendar_name = this.calendar_name;

		return new Promise((resolve) => {
			if (calendar_name === "default") {
				Object.assign(options, frappe.views.calendar[this.doctype]);
				resolve(options);
			} else {
				frappe.model.with_doc("Calendar View", calendar_name, () => {
					const doc = frappe.get_doc("Calendar View", calendar_name);
					if (!doc) {
						frappe.show_alert(
							__("{0} is not a valid Calendar. Redirecting to default Calendar.", [
								calendar_name.bold(),
							])
						);
						frappe.set_route("List", this.doctype, "Calendar", "default");
						return;
					}
					Object.assign(options, {
						field_map: {
							id: "name",
							start: doc.start_date_field,
							end: doc.end_date_field,
							title: doc.subject_field,
							allDay: doc.all_day ? 1 : 0,
						},
					});
					resolve(options);
				});
			}
		});
	}

	get required_libs() {
		return "calendar.bundle.js";
	}
};

frappe.views.Calendar = class Calendar {
	constructor(options) {
		$.extend(this, options);
		this.field_map = this.field_map || {
			id: "name",
			start: "start",
			end: "end",
			allDay: "all_day",
			convertToUserTz: "convert_to_user_tz",
		};
		this.color_map = {
			danger: "red",
			success: "green",
			warning: "orange",
			default: "blue",
		};
		this.get_default_options();
	}
	get_default_options() {
		return new Promise((resolve) => {
			let initialView = localStorage.getItem("cal_initialView");
			let weekends = localStorage.getItem("cal_weekends");
			let defaults = {
				initialView: initialView ? initialView : "dayGridMonth",
				weekends: weekends ? weekends : true,
			};
			resolve(defaults);
		}).then((defaults) => {
			this.make_page();
			this.setup_options(defaults);
			this.make();
			this.setup_view_mode_button(defaults);
			this.bind();
		});
	}
	make_page() {
		var me = this;

		// add links to other calendars
		me.page.clear_user_actions();
		$.each(frappe.boot.calendars, function (i, doctype) {
			if (frappe.model.can_read(doctype)) {
				me.page.add_menu_item(__(doctype), function () {
					frappe.set_route("List", doctype, "Calendar");
				});
			}
		});

		$(this.parent).on("show", function () {
			// (this used the FullCalendar v3 jQuery API — me.$cal.fullCalendar
			// is undefined on v6, so it threw on every page revisit)
			me.fullCalendar.refetchEvents();
			me.set_calendar_height();
		});
	}

	make() {
		this.$wrapper = this.parent;
		this.make_toolbar();
		// no horizontal padding of its own — the view container's rail is the
		// alignment edge for the toolbar, the grid and the footnote alike
		this.$cal = $("<div id='fc-calendar-wrapper' class='pt-3'>").appendTo(this.$wrapper);
		this.footnote_area = frappe.utils.set_footnote(
			this.footnote_area,
			this.$wrapper,
			__("Select or drag across time slots to create a new event.")
		);
		this.footnote_area.addClass("pb-4").css({
			"border-top": "0px",
		});
		this.fullCalendar = new frappe.FullCalendar(this.$cal[0], this.cal_options);
		this.fullCalendar.render();

		this.set_calendar_height();
		$(window).on(
			"resize.fc-calendar",
			frappe.utils.debounce(() => this.set_calendar_height(), 300)
		);
	}

	// size the calendar to the space left in the scroll column, so the view
	// fits the viewport instead of growing past it (FullCalendar's default
	// aspect-ratio sizing overflows on tall months)
	set_calendar_height() {
		if (!this.$cal.is(":visible")) return;
		const main = document.querySelector(".main-section");
		if (!main) return;
		const top = this.$cal[0].getBoundingClientRect().top - main.getBoundingClientRect().top;
		const footnote_height = this.footnote_area ? this.footnote_area.outerHeight(true) : 0;
		const available = main.clientHeight - top - footnote_height;
		this.fullCalendar.setOption("height", Math.max(available, 400));
	}

	// [prev] [title] [next] ........ [Month|Week|Day] [Today]
	// Month/Week/Day is a radio group (you are always in exactly one);
	// Today is an action, so it's a plain button
	make_toolbar() {
		this.$toolbar_title = $('<span class="text-lg-semibold text-ink-gray-8"></span>');
		this.view_button_group = new frappe.ui.TabButtons({
			label: __("Calendar View"),
			options: [
				{ label: __("Month"), value: "dayGridMonth" },
				{ label: __("Week"), value: "timeGridWeek" },
				{ label: __("Day"), value: "timeGridDay" },
			],
			value: this.cal_options.initialView,
			on_change: (value) => {
				this.fullCalendar.changeView(value);
				this.set_localStorage_option("cal_initialView", value);
			},
		});

		this.$toolbar = $('<div class="flex items-center gap-2 pt-4"></div>').append(
			frappe.ui.button({
				icon: "chevron-left",
				variant: "ghost",
				title: __("Previous"),
				onclick: () => this.fullCalendar.prev(),
			}),
			this.$toolbar_title,
			frappe.ui.button({
				icon: "chevron-right",
				variant: "ghost",
				title: __("Next"),
				onclick: () => this.fullCalendar.next(),
			}),
			$('<div class="grow"></div>'),
			this.view_button_group.$el,
			frappe.ui.button({
				label: __("Today"),
				onclick: () => this.fullCalendar.today(),
			})
		);
		this.$wrapper.append(this.$toolbar);
	}
	setup_view_mode_button(defaults) {
		$(this.footnote_area).find(".btn-weekend").detach();
		this.footnote_area.append(
			frappe.ui.button({
				label: defaults.weekends ? __("Hide Weekends") : __("Show Weekends"),
				size: "xs",
				css_class: "btn-weekend",
			})
		);
	}
	set_localStorage_option(option, value) {
		localStorage.removeItem(option);
		localStorage.setItem(option, value);
	}
	bind() {
		const me = this;
		me.$wrapper.on("click", ".btn-weekend", function () {
			me.cal_options.weekends = !me.cal_options.weekends;
			me.fullCalendar.setOption("weekends", me.cal_options.weekends);
			me.set_localStorage_option("cal_weekends", me.cal_options.weekends);
			me.setup_view_mode_button(me.cal_options);
		});
	}

	get_system_datetime(date) {
		return frappe.datetime.convert_to_system_tz(date, true);
	}
	setup_options(defaults) {
		var me = this;
		defaults.meridiem = "false";
		this.cal_options = {
			plugins: frappe.FullCalendar.Plugins,
			initialView: defaults.initialView || "dayGridMonth",
			locale: frappe.boot.lang,
			eventTimeFormat: {
				hour: "numeric",
				minute: "2-digit",
				hour12: true,
			},
			firstDay: frappe.datetime.get_first_day_of_the_week_index(),
			eventDisplay: "block",
			// the toolbar is ours (make_toolbar), not FullCalendar's — no
			// more stripping fc-button classes and re-adding them after every
			// re-render
			headerToolbar: false,
			datesSet: (info) => {
				this.$toolbar_title && this.$toolbar_title.text(info.view.title);
			},
			editable: true,
			droppable: true,
			selectable: true,
			selectMirror: true,
			forceEventDuration: true,
			displayEventTime: true,
			weekends: defaults.weekends,
			nowIndicator: true,
			themeSystem: null,
			buttonText: {
				today: __("Today"),
				month: __("Month"),
				week: __("Week"),
				day: __("Day"),
			},
			events: function (info, successCallback, failureCallback) {
				return frappe.call({
					method: me.get_events_method || "frappe.desk.calendar.get_events",
					type: "GET",
					args: me.get_args(info.start, info.end),
					callback: function (r) {
						var events = r.message || [];
						events = me.prepare_events(events);
						successCallback(events);
					},
				});
			},
			displayEventEnd: true,
			eventClick: function (info) {
				// edit event description or delete
				var doctype = info.doctype || me.doctype;
				if (frappe.model.can_read(doctype)) {
					frappe.set_route("Form", doctype, info.event.id);
				}
			},
			eventDrop: function (info) {
				me.update_event(info.event, info.revert);
			},
			eventResize: function (info) {
				me.update_event(info.event, info.revert);
			},
			select: function (info) {
				const seconds = info.end - info.start;
				const allDay = seconds === 86400000;

				if (info.view.type === "dayGridMonth" && allDay) {
					// detect single day click in month view
					return;
				}

				var event = frappe.model.get_new_doc(me.doctype);

				event[me.field_map.start] = me.get_system_datetime(info.start);
				if (me.field_map.end) event[me.field_map.end] = me.get_system_datetime(info.end);

				if (seconds >= 86400000) {
					if (allDay) {
						// all-day click
						event[me.field_map.allDay] = 1;
					}
					// incase of all day or multiple day events -1 sec
					event[me.field_map.end] = me.get_system_datetime(info.end - 1);
				}
				frappe.set_route("Form", me.doctype, event.name);
			},
			dateClick: function (info) {
				if (info.view.type === "dayGridMonth") {
					const $date_cell = $(
						"td[data-date=" + info.date.toISOString().slice(0, 10) + "]"
					);

					if ($date_cell.hasClass("date-clicked")) {
						me.fullCalendar.changeView("timeGridDay", info.date);
						me.$wrapper.find(".date-clicked").removeClass("date-clicked");

						// update "active view" btn
						me.$wrapper.find(".fc-month-button").removeClass("active");
						me.$wrapper.find(".fc-agendaDay-button").addClass("active");
					}

					me.$wrapper.find(".date-clicked").removeClass("date-clicked");
					$date_cell.addClass("date-clicked");

					// explicitly remove the fc primary button styling that is append on view change
					// from month -> day
					$("#fc-calendar-wrapper")
						.find("button.fc-button")
						.removeClass("fc-button fc-button-primary fc-button-active")
						.addClass("btn btn-default");
				}
				return false;
			},
		};

		if (this.options) {
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
			field_map: this.field_map,
		};
		return args;
	}
	refresh() {
		this.fullCalendar.refetchEvents();
	}
	prepare_events(events) {
		var me = this;

		return (events || []).map((d) => {
			d.id = d.name;
			d.editable = frappe.model.can_write(d.doctype || me.doctype);

			// do not allow submitted/cancelled events to be moved / extended
			if (d.docstatus && d.docstatus > 0) {
				d.editable = false;
			}

			$.each(me.field_map, function (target, source) {
				d[target] = d[source];
			});

			if (typeof d.allDay === "undefined") {
				d.allDay = me.field_map.allDay;
			}

			if (!me.field_map.convertToUserTz) d.convertToUserTz = 1;

			// convert to user tz
			if (d.convertToUserTz) {
				d.start = frappe.datetime.convert_to_user_tz(d.start);
				d.end = frappe.datetime.convert_to_user_tz(d.end);
			}

			// show event on single day if start or end date is invalid
			if (!frappe.datetime.validate(d.start) && d.end) {
				d.start = frappe.datetime.add_days(d.end, -1);
			}

			if (d.start && !frappe.datetime.validate(d.end)) {
				d.end = frappe.datetime.add_days(d.start, 1);
			}

			if (d.allDay && d.end) {
				d.end = frappe.datetime.add_days(d.end, 1);
			}

			me.prepare_colors(d);

			d.title = frappe.utils.html2text(d.title);

			return d;
		});
	}
	prepare_colors(d) {
		let color, color_name;
		if (this.get_css_class) {
			color_name = this.get_css_class(d);
			color_name = this.color_map[color_name] || color_name || "blue";

			if (color_name.startsWith("#")) {
				color_name = frappe.ui.color.validate_hex(color_name) ? color_name : "blue";
			}

			d.backgroundColor = frappe.ui.color.get(color_name, "extra-light");
			d.textColor = frappe.ui.color.get(color_name, "dark");
		} else {
			color = d.color;
			if (!frappe.ui.color.validate_hex(color) || !color) {
				color = frappe.ui.color.get("blue", "extra-light");
			}
			d.backgroundColor = color;
			d.textColor = frappe.ui.color.get_contrast_color(color);
		}
		return d;
	}
	update_event(event, revertFunc) {
		var me = this;
		frappe.model.remove_from_locals(me.doctype, event.id);
		return frappe.call({
			method: me.update_event_method || "frappe.desk.calendar.update_event",
			args: me.get_update_args(event),
			callback: function (r) {
				if (r.exc) {
					frappe.show_alert(__("Unable to update event"));
					revertFunc();
				}
			},
			error: function () {
				revertFunc();
			},
		});
	}
	get_update_args(event) {
		var me = this;
		var args = {
			name: event.id,
		};

		args[this.field_map.start] = me.get_system_datetime(event.start);

		if (this.field_map.allDay) {
			args[this.field_map.allDay] = event.end - event.start === 86400000 ? 1 : 0;
		}

		if (this.field_map.end) {
			if (!event.end) {
				event.end = event.start.add(1, "hour");
			}

			args[this.field_map.end] = me.get_system_datetime(event.end);
			if (args[this.field_map.allDay]) {
				args[this.field_map.end] = me.get_system_datetime(new Date(event.end - 1000));
			}
		}

		args.doctype = event.doctype || this.doctype;

		return { args: args, field_map: this.field_map };
	}
};
