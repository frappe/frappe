frappe.ui.form.ControlDate = class ControlDate extends frappe.ui.form.ControlData {
	static trigger_change_on_input_event = false;
	make_input() {
		super.make_input();
		this.make_picker();
	}
	make_picker() {
		this.set_date_options();
		this.set_datepicker();
		this.set_t_for_today();
	}
	set_formatted_input(value) {
		if (value === "Today") {
			value = this.get_now_date();
		}

		super.set_formatted_input(value);
		if (this.timepicker_only) return;
		if (!this.datepicker) return;
		if (!value) {
			this.datepicker.clear();
			return;
		}

		let should_refresh = this.last_value && this.last_value !== value;

		if (!should_refresh) {
			if (this.datepicker.selectedDates.length > 0) {
				// if date is selected but different from value, refresh
				const selected_date = moment(this.datepicker.selectedDates[0]).format(
					this.date_format
				);

				should_refresh = selected_date !== value;
			} else {
				// if datepicker has no selected date, refresh
				should_refresh = true;
			}
		}

		if (should_refresh) {
			const date_obj = frappe.datetime.str_to_obj(value);
			this.datepicker.selectDate(date_obj);
			this.datepicker.date = date_obj;
		}
	}
	set_date_options() {
		// webformTODO:
		let sysdefaults = frappe.boot.sysdefaults;

		let lang = "en";
		frappe.boot.user && (lang = frappe.boot.user.language);
		if (!$.fn.datepicker.language[lang]) {
			lang = "en";
		}

		let date_format =
			sysdefaults && sysdefaults.date_format ? sysdefaults.date_format : "yyyy-mm-dd";

		this.today_text = __("Today");
		this.date_format = frappe.defaultDateFormat;
		this.datepicker_options = {
			language: lang,
			autoClose: true,
			todayButton: true,
			dateFormat: date_format,
			startDate: this.get_start_date(),
			keyboardNav: false,
			minDate: this.df.min_date,
			maxDate: this.df.max_date,
			firstDay: frappe.datetime.get_first_day_of_the_week_index(),
			onSelect: () => {
				this.$input.trigger("change");
			},
			onShow: () => {
				this.datepicker.$datepicker
					.find(".datepicker--button:visible")
					.text(this.today_text);

				this.update_datepicker_position();
				this.sync_calendar_to_input();
			},
			onRenderCell: (date, cellType) => {
				if (cellType === "day" && this.df.disabled_dates) {
					const formattedDate = moment(date).format("YYYY-MM-DD");
					if (this.df.disabled_dates.includes(formattedDate)) {
						return {
							disabled: true,
							classes: "disabled",
						};
					}
				}
			},
			...this.get_df_options(),
		};
	}

	get_start_date() {
		let value = this.value || this.get_value();
		return (value && frappe.datetime.str_to_obj(value)) || this.get_now_date();
	}

	set_datepicker() {
		this.$input.datepicker(this.datepicker_options);
		this.datepicker = this.$input.data("datepicker");

		this.$input.on("input", () => {
			this.sync_calendar_to_input();
		});

		// today button didn't work as expected,
		// so explicitly bind the event
		this.datepicker.$datepicker.find('[data-action="today"]').click(() => {
			this.datepicker.selectDate(this.get_now_date());
			this.datepicker.hide();
		});
	}

	sync_calendar_to_input() {
		if (this.timepicker_only || !this.datepicker) return;

		let val = this.$input.val();
		if (!val) {
			this.datepicker.selectedDates = [];
			this.datepicker.views[this.datepicker.currentView]?._render();
			return;
		}

		let date_obj = this.parse_date_input(val);
		if (date_obj) {
			this.datepicker.selectedDates = [date_obj];
			this.datepicker.date = date_obj;
			if (this.datepicker.timepicker) {
				this.datepicker.timepicker._setTime(date_obj);
				this.datepicker.timepicker.update();
			}
		}
	}

	parse_date_input(val) {
		if (!val || typeof val !== "string") return null;
		val = val.trim();
		if (!val) return null;

		const user_fmt = frappe.datetime.get_user_date_fmt().toUpperCase();
		const date_formats = [
			user_fmt,
			user_fmt.replace("YYYY", "YY"),
			"YYYY-MM-DD",
			"DD-MM-YYYY",
			"DD/MM/YYYY",
			"DD.MM.YYYY",
			"MM-DD-YYYY",
			"MM/DD/YYYY",
			"YYYY/MM/DD",
			"DD-MM-YY",
			"DD/MM/YY",
			"DD.MM.YY",
			"YY-MM-DD",
			"MM-DD-YY",
			"MM/DD/YY",
		];

		const time_formats = ["HH:mm:ss", "hh:mm:ss A", "HH:mm", "hh:mm A"];
		const formats = [...date_formats];
		for (let df of date_formats) {
			for (let tf of time_formats) {
				formats.push(`${df} ${tf}`);
			}
		}

		const m = moment(val, formats, true);
		return m.isValid() ? m.toDate() : null;
	}
	update_datepicker_position() {
		if (!this.frm) return;
		// show datepicker above or below the input
		// based on scroll position
		// We have to bodge around the timepicker getting its position
		// wrong by 42px when opening upwards.
		const $header = $(".page-head");
		const header_bottom = $header.position().top + $header.outerHeight();
		const picker_height = this.datepicker.$datepicker.outerHeight() + 12;
		const picker_top = this.$input.offset().top - $(window).scrollTop() - picker_height;

		var position = "top left";
		// 12 is the default datepicker.opts[offset]
		if (picker_top <= header_bottom) {
			position = "bottom left";
			if (this.timepicker_only) this.datepicker.opts["offset"] = 12;
		} else {
			// To account for 42px incorrect positioning
			if (this.timepicker_only) this.datepicker.opts["offset"] = -30;
		}

		this.datepicker.update("position", position);
	}
	get_now_date() {
		return frappe.datetime
			.convert_to_system_tz(frappe.datetime.now_date(true), false)
			.toDate();
	}
	set_t_for_today() {
		var me = this;
		this.$input.on("keydown", function (e) {
			if (e.which === 84) {
				// 84 === t
				if (me.df.fieldtype == "Date") {
					me.set_value(frappe.datetime.nowdate());
				}
				if (me.df.fieldtype == "Datetime") {
					me.set_value(frappe.datetime.now_datetime());
				}
				if (me.df.fieldtype == "Time") {
					me.set_value(frappe.datetime.now_time());
				}
				return false;
			}
		});
	}
	parse(value) {
		if (value) {
			if (value == "Invalid date") {
				return "";
			}
			return frappe.datetime.user_to_str(value, false, true);
		}
	}
	format_for_input(value) {
		if (value) {
			return frappe.datetime.str_to_user(value, false, true);
		}
		return "";
	}
	validate(value) {
		if (value && !frappe.datetime.validate(value)) {
			let sysdefaults = frappe.sys_defaults;
			let date_format =
				sysdefaults && sysdefaults.date_format ? sysdefaults.date_format : "yyyy-mm-dd";
			frappe.msgprint(__("Date {0} must be in format: {1}", [value, date_format]));
			return "";
		}
		return value;
	}
	get_df_options() {
		let df_options = this.df.options;
		if (!df_options) return {};

		let options = {};
		if (typeof df_options === "string") {
			try {
				options = JSON.parse(df_options);
			} catch (error) {
				console.warn(`Invalid JSON in options of "${this.df.fieldname}"`);
			}
		} else if (typeof df_options === "object") {
			options = df_options;
		}
		return options;
	}
};
