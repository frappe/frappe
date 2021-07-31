frappe.ui.form.ControlDate = class ControlDate extends frappe.ui.form.ControlData {
	static trigger_change_on_input_event = false
	make_input() {
		super.make_input();
		this.make_picker();
	}
	make_picker() {
		this.set_date_options();
		this.set_datepicker();
		this.set_hotkeys();
	}
	set_formatted_input(value) {
		super.set_formatted_input(value);
		if (this.timepicker_only) return;
		if (!this.datepicker) return;
		if (!value) {
			this.datepicker.clear();
			return;
		} else if (value === "Today") {
			value = this.get_now_date();
		}

		let should_refresh = this.last_value && this.last_value !== value;

		if (!should_refresh) {
			if(this.datepicker.selectedDates.length > 0) {
				// if date is selected but different from value, refresh
				const selected_date =
					moment(this.datepicker.selectedDates[0])
						.format(this.date_format);

				should_refresh = selected_date !== value;
			} else {
				// if datepicker has no selected date, refresh
				should_refresh = true;
			}
		}

		if(should_refresh) {
			this.datepicker.selectDate(frappe.datetime.str_to_obj(value));
		}
	}
	set_date_options() {
		// webformTODO:
		let sysdefaults = frappe.boot.sysdefaults;

		let lang = 'en';
		frappe.boot.user && (lang = frappe.boot.user.language);
		if(!$.fn.datepicker.language[lang]) {
			lang = 'en';
		}

		let date_format = sysdefaults && sysdefaults.date_format
			? sysdefaults.date_format : 'yyyy-mm-dd';

		let now_date = new Date();

		this.today_text = __("Today");
		this.date_format = frappe.defaultDateFormat;
		this.datepicker_options = {
			language: lang,
			autoClose: true,
			todayButton: true,
			dateFormat: date_format,
			startDate: now_date,
			keyboardNav: false,
			onSelect: () => {
				this.$input.trigger('change');
			},
			onShow: () => {
				this.datepicker.$datepicker
					.find('.datepicker--button:visible')
					.text(this.today_text);

				this.update_datepicker_position();
			}
		};
	}
	set_datepicker() {
		this.$input.datepicker(this.datepicker_options);
		this.datepicker = this.$input.data('datepicker');

		// today button didn't work as expected,
		// so explicitly bind the event
		this.datepicker.$datepicker
			.find('[data-action="today"]')
			.click(() => {
				this.datepicker.selectDate(this.get_now_date());
			});
	}
	update_datepicker_position() {
		if(!this.frm) return;
		// show datepicker above or below the input
		// based on scroll position
		// We have to bodge around the timepicker getting its position
		// wrong by 42px when opening upwards.
		const $header = $('.page-head');
		const header_bottom = $header.position().top + $header.outerHeight();
		const picker_height = this.datepicker.$datepicker.outerHeight() + 12;
		const picker_top = this.$input.offset().top - $(window).scrollTop() - picker_height;

		var position = 'top left';
		// 12 is the default datepicker.opts[offset]
		if (picker_top <= header_bottom) {
			position = 'bottom left';
			if (this.timepicker_only) this.datepicker.opts['offset'] = 12;
		} else {
			// To account for 42px incorrect positioning
			if (this.timepicker_only) this.datepicker.opts['offset'] = -30;
		}

		this.datepicker.update('position', position);
	}
	get_now_date() {
		return frappe.datetime.now_date(true);
	}
	set_hotkeys() {
		var me = this;
		this.$input.on("keydown", function(e) {
			// example: 't' pressed (keyCode 84)
			// attempts to call function under me.hotkeys[84][<fieldtype>]
			if (e.which in me.hotkeys) {
				var keycode = e.which;
				if (typeof me.hotkeys[keycode] == 'number') {
					keycode = me.hotkeys[keycode]; // allows reusing of a key's event handler
				}

				if (me.df.fieldtype in me.hotkeys[keycode]) {
					if (me.hotkeys[keycode][me.df.fieldtype] instanceof Function) {
						me.hotkeys[keycode][me.df.fieldtype](me); // direct use
					} else {
						me.hotkeys[keycode][me.hotkeys[keycode][me.df.fieldtype]](me); // allows reusing of a key's event handler
					}
					return false;
				}
			}
		});
	}
	
	hotkeys = {
		// Hotkey event handling=================
		//
		// // <keycode explanatory comment>
		// <keyCode>: {
		//		'<fieldtype>': function(control_instance) { ... }
		//				OR
		//		'<fieldtype>': '<other set fieldtype>'
		// },
		//
		//				OR
		//
		// // <keycode explanatory comment>
		// <keyCode>: <other set keyCode>,
		//
		//=======================================
		// For reference:
		// 		https://intuitglobal.intuit.com/iq/quickbooks/docs/QB_Shortcut_Keys.pdf under "Dates"
		//=======================================
		//
		// 84 === 't' - (t)oday
		84: {
			'Date': function(control) {
				control.set_value(frappe.datetime.nowdate());
			},
			'Datetime': function(control) {
				control.set_value(frappe.datetime.now_datetime());
			},
			'Time': function(control) {
				control.set_value(frappe.datetime.now_time());
			}
		},
		// 89 === 'y' - First day of (y)ear
		89: {
			'Date': function(control) {
				if (frappe.datetime.get_diff(frappe.datetime.year_start_of(control.get_value()), control.get_value()) === 0) {
					control.set_value(frappe.datetime.subtract(control.get_value(), 1, "years"));
				} else {
					control.set_value(frappe.datetime.year_start_of(control.get_value()));
				}
			},
			'Datetime': 'Date',
		},
		// 82 === 'r' - Last day of yea(r)
		82: {
			'Date': function(control) {
				if (frappe.datetime.get_diff(frappe.datetime.year_end_of(control.get_value()), control.get_value()) === 0) {
					control.set_value(frappe.datetime.add(control.get_value(), 1, "year"));
				} else {
					control.set_value(frappe.datetime.year_end_of(control.get_value()));
				}
			},
			'Datetime': 'Date',
		},
		// 77 === 'm' - First day of (m)onth
		77: {
			'Date': function(control) {
				if (frappe.datetime.get_diff(frappe.datetime.month_start_of(control.get_value()), control.get_value()) === 0) {
					control.set_value(frappe.datetime.subtract(control.get_value(), 1, "months"));
				} else {
					control.set_value(frappe.datetime.month_start_of(control.get_value()));
				}
			},
			'Datetime': 'Date',
		},
		// 72 === 'h' - Last day of mont(h)
		72: {
			'Date': function(control) {
				if (frappe.datetime.get_diff(frappe.datetime.month_end_of(control.get_value()), control.get_value()) === 0) {
					control.set_value(frappe.datetime.add(control.get_value(), 1, "months"));
				} else {
					control.set_value(frappe.datetime.month_end_of(control.get_value()));
				}
			},
			'Datetime': 'Date',
		},
		// 87 === 'w' - First day of (w)eek
		87: {
			'Date': function(control) {
				if (frappe.datetime.get_diff(frappe.datetime.week_start_of(control.get_value()), control.get_value()) === 0) {
					control.set_value(frappe.datetime.subtract(control.get_value(), 1, "weeks"));
				} else {
					control.set_value(frappe.datetime.week_start_of(control.get_value()));
				}
			},
			'Datetime': 'Date',
		},
		// 75 === 'k' - Last day of wee(k)
		75: {
			'Date': function(control) {
				if (frappe.datetime.get_diff(frappe.datetime.week_end_of(control.get_value()), control.get_value()) === 0) {
					control.set_value(frappe.datetime.add(control.get_value(), 1, "weeks"));
				} else {
					control.set_value(frappe.datetime.week_end_of(control.get_value()));
				}
			},
			'Datetime': 'Date',
		},
		// 107 === numpad '+' - Next Day
		107: {
			'Date': function(control) {
				control.set_value(frappe.datetime.add_days(control.get_value(), 1));
			},
			'Datetime': 'Date',
		},
		// 61 === '+'
		61: 107,
		// 109 === numpad '-' - Previous Day
		109: {
			'Date': function(control) {
				control.set_value(frappe.datetime.subtract_days(control.get_value(), 1));
			},
			'Datetime': 'Date',
		},
		// 173 === '-'
		173: 109,
	};

	parse(value) {
		if(value) {
			return frappe.datetime.user_to_str(value);
		}
	}
	format_for_input(value) {
		if(value) {
			return frappe.datetime.str_to_user(value);
		}
		return "";
	}
	validate(value) {
		if(value && !frappe.datetime.validate(value)) {
			let sysdefaults = frappe.sys_defaults;
			let date_format = sysdefaults && sysdefaults.date_format
				? sysdefaults.date_format : 'yyyy-mm-dd';
			frappe.msgprint(__("Date {0} must be in format: {1}", [value, date_format]));
			return '';
		}
		return value;
	}
};
