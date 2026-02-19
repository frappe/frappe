frappe.ui.form.ControlInt = class ControlInt extends frappe.ui.form.ControlData {
	static trigger_change_on_input_event = false;
	static input_mode = "numeric";
	make() {
		super.make();
	}
	make_input() {
		super.make_input();
		this.$input.on("focus", () => {
			document.activeElement?.select?.();
			return false;
		});
	}
	validate(value) {
		return this.parse(value);
	}
<<<<<<< HEAD
	eval_expression(value) {
		if (typeof value === "string") {
			const parsed_components = value.match(/[^\d.,]+|[\d.,]+/g);
			var parsed_value = value;
			if (parsed_components !== null) {
				parsed_value = parsed_components
					.map((v) => {
						return isNaN(parseFloat(v)) ? v : flt(v);
					})
					.join("");
			}
			if (parsed_value.match(/^[0-9+\-/*.() ]+$/)) {
				// If it is a string containing operators
				try {
					return eval(parsed_value);
				} catch (e) {
					// bad expression
					return value;
				}
			}
		}
		return value;
=======
	eval_expression(value, number_format) {
<<<<<<< HEAD
		return typeof value === "string" ? frappe.utils.eval_expression(value, number_format) : value;
>>>>>>> fa5cc11c92 (fix: use super.eval_expression in ControlFloat instead of full override)
=======
		return typeof value === "string"
			? frappe.utils.eval_expression(value, number_format)
			: value;
>>>>>>> 67183e456e (style: fix prettier formatting in ControlInt.eval_expression)
	}
	parse(value) {
		return cint(this.eval_expression(value), null);
	}
};

frappe.ui.form.ControlLongInt = frappe.ui.form.ControlInt;
