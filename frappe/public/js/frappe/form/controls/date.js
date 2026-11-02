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
			this.clear_datepicker();
			this.datepicker.setViewDate(this.get_now_date());
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
			const date = frappe.datetime.str_to_obj(value);
			this.select_date_silently(date);
			this.datepicker.setViewDate(date);
		}
	}
	select_date_silently(date, opts) {
		this.update_datepicker_silently(() =>
			this.datepicker.selectDate(date, { silent: true, ...opts })
		);
	}
	clear_datepicker() {
		if (!this.datepicker.selectedDates.length) return;
		this.update_datepicker_silently(() => this.datepicker.clear({ silent: true }));
	}
	update_datepicker_silently(fn) {
		this._suppress_change = true;
		fn();
		setTimeout(() => (this._suppress_change = false));
	}
	set_date_options() {
		this.today_text = __("Today");
		this.date_format = frappe.defaultDateFormat;
		this.datepicker_options = {
			locale: frappe.ui.form.get_datepicker_locale(),
			autoClose: true,
			buttons: [this.get_today_button()],
			dateFormat: (date) => frappe.datetime.obj_to_user(date),
			startDate: this.get_start_date(),
			keyboardNav: false,
			minDate: this.df.min_date,
			maxDate: this.df.max_date,
			firstDay: frappe.datetime.get_first_day_of_the_week_index(),
			position: frappe.ui.form.position_datepicker,
			onRenderCell: ({ date, cellType }) => {
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

	get_today_button() {
		return {
			content: () => this.today_text,
			onClick: (datepicker) => {
				datepicker.selectDate(this.get_now_date(), { updateTime: true });
				if (datepicker.visible) datepicker.hide();
			},
		};
	}

	get_start_date() {
		return this.get_now_date();
	}

	set_datepicker() {
		this.datepicker = new AirDatepicker(this.$input[0], this.datepicker_options);
		this.$input[0].addEventListener(
			"change",
			(e) => this._suppress_change && e.stopImmediatePropagation(),
			true
		);
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

	eval_expression(value, type) {
		if (!value || !type) {
			return value;
		}
		const parsed_components = value.match(/[\+\-]\s*\d*\.?\d+\s*[a-zA-Z]/g);

		let system_fmt;
		switch (type) {
			case "date":
				system_fmt = "YYYY-MM-DD";
				value = frappe.datetime.user_to_str(value, false);
				break;

			case "time":
				system_fmt = "HH:mm:ss";
				value = frappe.datetime.user_to_str(value, true);
				break;

			case "datetime":
				system_fmt = "YYYY-MM-DD HH:mm:ss";
				value = frappe.datetime.user_to_str(value, false);
				break;
		}

		if (!parsed_components) {
			return value;
		}

		let time_to_add = {};
		parsed_components.forEach((component) => {
			let operator = component.match(/[\+\-]/)[0];
			let number = flt(component.match(/\d*\.?\d+/)[0]);
			let unit = component.match(/[a-zA-Z]+/)[0];
			let period;

			if (operator === "-") {
				number = -number;
			}

			if (["datetime", "date"].includes(type)) {
				if (unit.toLowerCase() === "d") {
					period = "days";
				} else if (unit === "M") {
					period = "months";
				} else if (unit.toLowerCase() === "y") {
					period = "years";
				}
			}

			if (["datetime", "time"].includes(type)) {
				if (unit.toLowerCase() === "h") {
					period = "hours";
				} else if (unit === "m") {
					period = "minutes";
				} else if (unit.toLowerCase() === "s") {
					period = "seconds";
				}
			}

			if (period) {
				time_to_add[period] = (time_to_add[period] || 0) + number;
			}
		});

		if (Object.keys(time_to_add).length) {
			value = moment(value, system_fmt).add(time_to_add).format(system_fmt);
		}

		return value;
	}

	parse(value) {
		if (value) {
			if (value == "Invalid date") {
				return "";
			}
			return this.eval_expression(value, "date");
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

frappe.ui.form.position_datepicker = ({ $datepicker, $target }) => {
	const offset = 4;
	const input = $target.getBoundingClientRect();
	const picker = $datepicker.getBoundingClientRect();
	const space_below = window.innerHeight - input.bottom;
	const above = space_below < picker.height + offset && input.top > picker.height + offset;
	const top = above ? input.top - picker.height - offset : input.bottom + offset;
	const left = frappe.utils.is_rtl() ? input.right - picker.width : input.left;
	$datepicker.style.top = `${top + window.scrollY}px`;
	$datepicker.style.left = `${Math.max(left, 0) + window.scrollX}px`;
};
