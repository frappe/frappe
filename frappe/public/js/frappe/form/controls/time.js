frappe.ui.form.ControlTime = class ControlTime extends frappe.ui.form.ControlDate {
	set_formatted_input(value) {
		super.set_formatted_input(value);
	}
	make_input() {
		this.timepicker_only = true;
		super.make_input();
	}
	make_picker() {
		this.set_time_options();
		this.set_datepicker();
		this.refresh();
	}
	set_time_options() {
		let sysdefaults = frappe.boot.sysdefaults;

		let time_format =
			sysdefaults && sysdefaults.time_format ? sysdefaults.time_format : "HH:mm:ss";

		this.time_format = frappe.defaultTimeFormat;
		this.today_text = __("Now");
		this.datepicker_options = {
			locale: frappe.ui.form.get_datepicker_locale("en"),
			timepicker: true,
			onlyTimepicker: true,
			timeFormat: time_format.replace(":ss", ""),
			dateFormat: (date) => moment(date).format(time_format),
			startDate: frappe.datetime.now_time(true),
			position: frappe.ui.form.position_datepicker,
			keyboardNav: false,
			buttons: [this.get_today_button()],
		};
	}
	set_datepicker() {
		super.set_datepicker();
		frappe.ui.form.add_seconds_slider(this.datepicker);
	}
	get_now_date() {
		return frappe.datetime.now_time(true);
	}
	set_input(value) {
		super.set_input(value);
		if (!this.datepicker) {
			return;
		}
		if (!value) {
			this.clear_datepicker();
			return;
		}

		// sync the picker, else it writes its stale time back into the input when shown
		const selected_date = this.datepicker.selectedDates[0];
		const selected_time =
			selected_date && moment(selected_date).format(frappe.defaultTimeFormat);
		const time = moment(value, frappe.defaultTimeFormat);
		if (selected_time !== time.format(frappe.defaultTimeFormat)) {
			this.select_date_silently(frappe.datetime.moment_to_date_obj(time), {
				updateTime: true,
			});
		}
	}
	set_description() {
		const description = this.df.description
			? __(this.df.description, null, this.df.parent)
			: this.df.description;
		const { time_zone } = frappe.sys_defaults;
		if (!frappe.datetime.is_system_time_zone()) {
			if (!description) {
				this.df.description = time_zone;
			} else if (!description.includes(time_zone)) {
				this.df.description = description + "<br>" + time_zone;
			}
		}
		super.set_description();
	}
	parse(value) {
		if (value) {
			if (value == "Invalid date") {
				value = "";
			}
			return this.eval_expression(value, "time");
		}
	}
	format_for_input(value) {
		if (value) {
			return frappe.datetime.str_to_user(value, true);
		}
		return "";
	}
	validate(value) {
		if (value && !frappe.datetime.validate(value)) {
			let sysdefaults = frappe.sys_defaults;
			let time_format =
				sysdefaults && sysdefaults.time_format ? sysdefaults.time_format : "HH:mm:ss";
			frappe.msgprint(__("Time {0} must be in format: {1}", [value, time_format]));
			return "";
		}
		return value;
	}
};
