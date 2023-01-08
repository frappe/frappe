frappe.ui.form.ControlDatetime = class ControlDatetime extends frappe.ui.form.ControlDate {
	set_formatted_input(value) {
		super.set_formatted_input(value);
		if (this.timepicker_only) return;
		if (!this.datepicker) return;
		if (!value) {
			this.datepicker.clear();
			return;
		} else if (value.toLowerCase() === "today") {
			value = this.get_now_date();
		} else if (value.toLowerCase() === "now") {
			value = frappe.datetime.now_datetime();
		}
		value = this.format_for_input(value);
		this.$input && this.$input.val(value);
		this.datepicker.selectDate(frappe.datetime.user_to_obj(value));
	}

	get_start_date() {
		this.value = this.value == null ? undefined : this.value;
		let value = frappe.datetime.convert_to_user_tz(this.value);
		return frappe.datetime.str_to_obj(value);
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
		return frappe.datetime.now_datetime(true);
	}
	parse(value) {
		if (value) {
			value = frappe.datetime.user_to_str(value, false);
			if (!frappe.datetime.is_system_time_zone()) {
				value = frappe.datetime.convert_to_system_tz(value, true);
			}

			if (value == "Invalid date") {
				value = "";
			}
		}
		return value;
	}
	format_for_input(value) {
		if (!value) return "";
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
		return frappe.boot.time_zone ? frappe.boot.time_zone.user : frappe.sys_defaults.time_zone;
	}
	set_datepicker() {
		let sysdefaults = frappe.boot.sysdefaults;
		let user_fmt = frappe.datetime.get_user_date_fmt().replace("mm", "MM");
		let user_time_fmt = frappe.datetime.get_user_time_fmt();
		let datetime_fmt = user_fmt + " " + user_time_fmt

		let lang = "en";
		frappe.boot.user && (lang = frappe.boot.user.language);
		if (!$.fn.datepicker.language[lang]) {
			lang = "en";
		}

		this.load_lib().then(() => {
			const customdate = require("./tempus-dominus/plugins/customDateFormat.js");
			tempusDominus.extend(customdate);
				new tempusDominus.TempusDominus(document.querySelector(`[data-fieldname="${this.df.fieldname}"]`), {
				display: {
					components: {
					decades: false,
					year: true,
					month: true,
					date: true,
					hours: true,
					minutes: true,
					seconds: user_time_fmt.endsWith("ss")
					},
					icons: {
						type: 'sprites',
						time: '#icon-select',
						date: '#icon-select',
						up: '#icon-small-up',
						down: '#icon-down',
						previous: '#icon-left',
						next: '#icon-right',
						today: '#icon-today',
						clear: '#icon-refresh',
						close: '#icon-close-alt'
					},
					theme: 'dark',
					buttons: {
						today: true,
						clear: true,
						close: true
					  }
				},
				localization: {
					format: datetime_fmt,
				  }
		  });
		});
		this.$input.attr("inputmode", "none");
	}

	get_model_value() {
		let value = super.get_model_value();
		if (!value && !this.doc) {
			value = this.last_value;
		}
		return !value ? "" : value;
	}

	load_lib() {
		return new Promise((resolve) => {
			var asset_dir = "/assets/frappe/js/lib/tempus-dominus/";
			frappe.require(
				[
					asset_dir + "tempus-dominus.css",
					asset_dir + "tempus-dominus.js",
					asset_dir + "popper.min.js",
				],
				resolve
			);
		});
	}
};
