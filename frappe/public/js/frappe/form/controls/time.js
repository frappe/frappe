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
	set_input(value) {
		super.set_input(value);
		if (!this.datepicker) {
			return;
		}
		if (!value) {
			this.datepicker.clear();
			return;
		}

		let should_refresh = this.last_value && this.last_value !== value;
		let time_format = frappe.sys_defaults.time_format || "HH:mm:ss";
		if (!should_refresh) {
			if (this.datepicker.selectedDates.length > 0) {
				// if time is selected but different from value, refresh
				const selected_date = moment(this.datepicker.selectedDates[0]).format(
					this.time_format
				);

				should_refresh = selected_date !== value;
			} else {
				// if datepicker has no selected time, refresh
				should_refresh = true;
			}
		}

		if (should_refresh) {
			this.datepicker.selectDate(
				frappe.datetime.moment_to_date_obj(moment(value, time_format))
			);
		}
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
	set_description() {
		const { description } = this.df;
		const { time_zone } = frappe.sys_defaults;
		if (!frappe.datetime.is_system_time_zone()) {
			if (!description) {
				this.df.description = time_zone;
			} else if (!description.includes(time_zone)) {
				this.df.description += "<br>" + time_zone;
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
