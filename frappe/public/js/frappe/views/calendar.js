// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.views.calendar");
frappe.provide("frappe.views.calendars");

frappe.views.Calendar = Class.extend({
	init: function(options) {
		$.extend(this, options);
		this.make_page();
		this.setup_options();
		this.make();
	},
	make_page: function() {
		var me = this;

		$(this.parent).on("show", function() {
			me.set_filters_from_route_options();
		});

		var module = locals.DocType[this.doctype].module;
		this.page.set_title(__("Calendar") + " - " + __(this.doctype));

		frappe.breadcrumbs.add(module, this.doctype);

		this.page.set_primary_action(__("New"), function() {
			var doc = frappe.model.get_new_doc(me.doctype);
			frappe.set_route("Form", me.doctype, doc.name);
		});

		// add links to other calendars
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
		footnote = frappe.utils.set_footnote(this, this.$wrapper,
			__("Select or drag across time slots to create a new event."));
		footnote.css({"border-top": "0px"});

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
	styles: {
		"standard": {
			"color": "#F0F4F7"
		},
		"important": {
			"color": "#FFDCDC"
		},
		"danger": {
			"color": "#FFDCDC"
		},
		"warning": {
			"color": "#FFE6BF",
		},
		"success": {
			"color": "#E4FFC1",
		},
		"info": {
			"color": "#E8DDFF"
		},
		"inverse": {
			"color": "#D9F6FF"
		},
		"": {
			"color": "#F0F4F7"
		}
	},
	get_system_datetime: function(date) {
		date._offset = moment.user_utc_offset;
		return frappe.datetime.convert_to_system_tz(date);
	},
	setup_options: function() {
		var me = this;
		this.cal_options = {
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
						me.prepare_events(events);
						callback(events);
					}
				})
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
			dayClick: function(date, allDay, jsEvent, view) {
				jsEvent.day_clicked = true;
				return false;
			}
		};

		if(this.options) {
			$.extend(this.cal_options, this.options);
		}
	},
	get_args: function(start, end) {
		if(this.filter_vals) {
			var filters = {};
			this.filter_vals.forEach(function(f) {
				if(f[2]==="=") {
					filters[f[1]] = f[3];
				}
			});
		}
		var args = {
			doctype: this.doctype,
			start: this.get_system_datetime(start),
			end: this.get_system_datetime(end),
			filters: filters
		};
		return args;
	},
	refresh: function() {
		this.$cal.fullCalendar('refetchEvents');
	},
	prepare_events: function(events) {
		var me = this;
		$.each(events || [], function(i, d) {
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

			if(me.get_css_class) {
				$.extend(d, me.styles[me.get_css_class(d)] || {});
			} else if(me.style_map) {
				$.extend(d, me.styles[me.style_map[d.status]] || {});
			} else {
				$.extend(d, me.styles[frappe.utils.guess_style(d.status, "standard")]);
			}
			d["textColor"] = "#36414C";
		})
	},
	update_event: function(event, revertFunc) {
		var me = this;
		frappe.model.remove_from_locals(me.doctype, event.name);
		return frappe.call({
			method: me.update_event_method || "frappe.desk.calendar.update_event",
			args: me.get_update_args(event),
			callback: function(r) {
				if(r.exc) {
					show_alert(__("Unable to update event"));
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
	},
	add_filters: function() {
		var me = this;
		if(this.filters) {
			$.each(this.filters, function(i, df) {
				df.change = function() {
					me.refresh();
				};
				me.page.add_field(df);
			});
		}
	},
	set_filter: function(doctype, value) {
		var me = this;
		if(this.filters) {
			$.each(this.filters, function(i, df) {
				if(df.options===value)
					me.page.fields_dict[df.fieldname].set_input(value);
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
					me.page.fields_dict[df.fieldname || df.label].get_parsed_value();
			});
		}
		return filter_vals;
	},
	set_filters_from_route_options: function() {
		var me = this;
		if(frappe.route_options) {
			$.each(frappe.route_options, function(k, value) {
				if(me.page.fields_dict[k]) {
					me.page.fields_dict[k].set_input(value);
				};
			})
			frappe.route_options = null;
			me.refresh();
			return false;
		}
	}
})
