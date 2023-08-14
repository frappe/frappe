frappe.ui.form.ControlTime = class ControlTime extends frappe.ui.form.ControlDatetime {
	date_to_value(obj) {
		return obj.toISOString().substring(11, 19);
	}

	value_to_date(value) {
		if (!value) return new Date();
		const time_format = frappe.sys_defaults.time_format || "HH:mm:ss";
		return frappe.datetime.moment_to_date_obj(moment(value, time_format));
		// return frappe.datetime.str_to_obj(`1970-01-01T${value}`);
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
		this.datepicker_options = {
			language: "en",
			timepicker: true,
			onlyTimepicker: true,
			timeFormat: time_format.toLowerCase().replace("mm", "ii"),
			startDate: frappe.datetime.now_time(true),
			onSelect: () => {
				// ignore micro seconds
				if (
					moment(this.get_value(), time_format).format("HH:mm:ss") !=
					moment(this.value, time_format).format("HH:mm:ss")
				) {
					this.$input.trigger("change");
				}
			},
			onShow: () => {
				$(".datepicker--button:visible").text(__("Now"));

				this.update_datepicker_position();
			},
			keyboardNav: false,
			todayButton: true,
		};
	}

	set_datepicker() {
		this.$input.datepicker(this.datepicker_options);
		this.datepicker = this.$input.data("datepicker");

		this.datepicker.$datepicker.find('[data-action="today"]').click(() => {
			this.datepicker.selectDate(frappe.datetime.now_time(true));
			this.datepicker.hide();
		});
		if (this.datepicker.opts.timeFormat.indexOf("s") == -1) {
			// No seconds in time format
			const $tp = this.datepicker.timepicker;
			$tp.$seconds.parent().css("display", "none");
			$tp.$secondsText.css("display", "none");
			$tp.$secondsText.prev().css("display", "none");
		}
	}

	get_user_time_zone() {
		return frappe.boot.time_zone?.system || frappe.sys_defaults.time_zone;
	}

	parse(value) {
		let parsed = typeof value === "string" ? value.trim() : "";

		if (["today", "now"].includes(parsed.toLowerCase())) {
			parsed = frappe.datetime.now_time(false);
		} else if (parsed) {
			parsed = frappe.datetime.user_to_str(parsed, true);
		}

		if (parsed === "Invalid date") {
			console.warn("Invalid time", value); // eslint-disable-line
			parsed = "";
		}

		return parsed;
	}

	format_for_input(value) {
		if (!value) return "";
		// value = frappe.datetime.convert_to_user_tz(value, true);
		return frappe.datetime.str_to_user(value, true);
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
