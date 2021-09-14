frappe.ui.form.ControlFloat = class ControlFloat extends frappe.ui.form.ControlInt {

	make_input() {
		super.make_input();
		const change_handler = e => {
			if (this.change) this.change(e);
			else {
				let value = this.get_input_value();
				this.parse_validate_and_set_in_model(value, e);
			}
		};
		// convert to number format on focusout since focus converts it to flt.
		this.$input.on("focusout", change_handler);
	}
	parse(value) {
		value = this.eval_expression(value);
		return isNaN(parseFloat(value)) ? null : flt(value, this.get_precision());
	}

	format_for_input(value) {
		var number_format;
		if (this.df.fieldtype==="Float" && this.df.options && this.df.options.trim()) {
			number_format = this.get_number_format();
		}
		var formatted_value = format_number(value, number_format, this.get_precision());
		return isNaN(Number(value)) ? "" : formatted_value;
	}

	get_number_format() {
		var currency = frappe.meta.get_field_currency(this.df, this.get_doc());
		return get_number_format(currency);
	}

	get_precision() {
		// round based on field precision or float precision, else don't round
		return this.df.precision || cint(frappe.boot.sysdefaults.float_precision, null);
	}
};

frappe.ui.form.ControlPercent = frappe.ui.form.ControlFloat;
