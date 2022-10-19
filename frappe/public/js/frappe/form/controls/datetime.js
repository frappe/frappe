<<<<<<< HEAD
frappe.ui.form.ControlDatetime = frappe.ui.form.ControlDate.extend({
	set_date_options: function() {
		this._super();
=======
frappe.ui.form.ControlDatetime = class ControlDatetime extends frappe.ui.form.ControlDate {
	set_formatted_input(value) {
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
>>>>>>> 5bbb9b42e1 (fix: consider now datetime if the default value is now for datetime field)
		this.today_text = __("Now");
		let sysdefaults = frappe.boot.sysdefaults;
		this.date_format = frappe.defaultDatetimeFormat;
		let time_format = sysdefaults && sysdefaults.time_format
			? sysdefaults.time_format : 'HH:mm:ss';
		$.extend(this.datepicker_options, {
			timepicker: true,
			timeFormat: time_format.toLowerCase().replace("mm", "ii")
		});
	},
	get_now_date: function() {
		return frappe.datetime.now_datetime(true);
	},
	set_description: function() {
		const { description } = this.df;
		const { time_zone } = frappe.sys_defaults;
		if (!this.df.hide_timezone && !frappe.datetime.is_timezone_same()) {
			if (!description) {
				this.df.description = time_zone;
			} else if (!description.includes(time_zone)) {
				this.df.description += '<br>' + time_zone;
			}
		}
		this._super();
	},
	set_datepicker: function() {
		this._super();
		if (this.datepicker.opts.timeFormat.indexOf('s') == -1) {
			// No seconds in time format
			const $tp = this.datepicker.timepicker;
			$tp.$seconds.parent().css('display', 'none');
			$tp.$secondsText.css('display', 'none');
			$tp.$secondsText.prev().css('display', 'none');
		}
	},
	get_model_value() {
		let value = this._super();
		return !value ? "" : frappe.datetime.get_datetime_as_string(value);
	}
});
