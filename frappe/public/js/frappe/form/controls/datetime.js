frappe.ui.form.ControlDatetime = class ControlDatetime extends frappe.ui.form.ControlDate {
	set_formatted_input(value) {
		super.set_formatted_input(value);
		value = this.format_for_input(value);
		this.$input && this.$input.val(value);
	}

	get_start_date() {
		this.value = this.value == null ? undefined : this.value;
		let value = frappe.datetime.convert_to_user_tz(this.value);
		return frappe.datetime.str_to_obj(value);
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
	set_datepicker() {
		this.$input.attr("type", "datetime-local");
		if (frappe.datetime.get_user_time_fmt() == "HH:mm:ss") {
			this.$input.attr("step", "1");
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
