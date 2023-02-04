frappe.ui.form.ControlTime = class ControlTime extends frappe.ui.form.ControlDate {
	set_formatted_input(value) {
		super.set_formatted_input(value);
	}
	make_input() {
		//this.timepicker_only = true;
		super.make_input();
	}
	make_picker() {
		this.set_datepicker();
	}
	set_input(value) {
		super.set_input(value);
	}
	set_datepicker() {
		this.$input.attr("type", "time");
		if (frappe.datetime.get_user_time_fmt() == "HH:mm:ss") {
			this.$input.attr("step", "1");
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
			return frappe.datetime.user_to_str(value, true);
		}
	}
	format_for_input(value) {
		if (value) {
			return frappe.datetime.str_to_user(value, true);
		}
		return "";
	}
};
