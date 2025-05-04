frappe.ui.form.ControlTime = class ControlTime extends frappe.ui.form.ControlData {
	static input_type = "time";

	make_input() {
		super.make_input();
		this.set_step();
		this.set_t_for_today();
	}

	set_step() {
		if (this.show_seconds()) {
			this.$input.attr("step", 1); // show seconds picker
		}
	}

	show_seconds() {
		return frappe.boot.sysdefaults?.time_format !== "HH:mm";
	}

	set_t_for_today() {
		this.$input.on("keydown", (e) => {
			if (e.which !== 84) {
				// 84 === t
				return;
			}

			this.set_value(frappe.datetime.now_time());
			return false;
		});
	}

	set_value(value, force_set_value = false) {
		if (value && !this.show_seconds()) {
			return this.validate_and_set_in_model(
				this.strip_seconds(value),
				null,
				force_set_value
			);
		}

		return this.validate_and_set_in_model(value, null, force_set_value);
	}

	get_model_value() {
		const value = super.get_model_value();
		if (value && !this.show_seconds()) {
			return this.strip_seconds(value);
		}
		return value;
	}

	strip_seconds(value) {
		return value.split(":").slice(0, 2).join(":");
	}
};
