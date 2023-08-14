frappe.ui.form.ControlDatetime = class ControlDatetime extends frappe.ui.form.ControlDate {
	date_to_value(obj) {
		return obj.toISOString().split(/[.+Z]/)[0].replace("T", " ");
	}

	value_to_date(value) {
		const str = frappe.datetime.convert_to_user_tz(value, true);
		return frappe.datetime.str_to_obj(str);
	}

	set_date_options() {
		super.set_date_options();
		this.today_text = __("Now");
		let sysdefaults = frappe.boot.sysdefaults;
		this.date_format = frappe.defaultDatetimeFormat;
		let time_format =
			sysdefaults && sysdefaults.time_format ? sysdefaults.time_format : "HH:mm:ss";
		$.extend(this.datepicker_options, {
			timepicker: true,
			timeFormat: time_format.toLowerCase().replace("mm", "ii"),
		});
	}

	get_now_date() {
		return frappe.datetime
			.convert_to_system_tz(frappe.datetime.now_date(true), false)
			.toDate();
	}

	/** @param {string | null} value */
	parse(value) {
		let parsed = typeof value === "string" ? value.trim() : "";

		if (["today", "now"].includes(parsed.toLowerCase())) {
			parsed = frappe.datetime.now_datetime(false);
		} else if (parsed) {
			parsed = frappe.datetime.user_to_str(parsed, false);
			parsed = frappe.datetime.convert_to_system_tz(parsed, true);
		}

		if (parsed === "Invalid date") {
			console.warn("Invalid datetime", value); // eslint-disable-line
			parsed = "";
		}

		return parsed;
	}

	format_for_input(value) {
		if (!value) return "";
		value = frappe.datetime.convert_to_user_tz(value, true);
		return frappe.datetime.str_to_user(value, false);
	}

	set_description() {
		const description = this.df.description;
		const time_zone = this.get_user_time_zone();

		if (!this.df.hide_timezone) {
			// Always show the timezone when rendering the Datetime field since the datetime value will
			// always be in system_time_zone rather then local time.

			if (!description) {
				this.df.description = time_zone;
			} else if (!description.includes(time_zone)) {
				this.df.description += "<br>" + time_zone;
			}
		}
		super.set_description();
	}

	get_user_time_zone() {
		return frappe.boot.time_zone?.user || frappe.sys_defaults.time_zone;
	}

	set_datepicker() {
		super.set_datepicker();
		if (this.datepicker.opts.timeFormat.indexOf("s") == -1) {
			// No seconds in time format
			const $tp = this.datepicker.timepicker;
			$tp.$seconds.parent().css("display", "none");
			$tp.$secondsText.css("display", "none");
			$tp.$secondsText.prev().css("display", "none");
		}
	}

	get_model_value() {
		let value = super.get_model_value();
		if (!value && !this.doc) {
			value = this.last_value;
		}
		return !value ? "" : frappe.datetime.get_datetime_as_string(value);
	}
};
