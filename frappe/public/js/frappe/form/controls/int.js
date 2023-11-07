frappe.ui.form.ControlInt = class ControlInt extends frappe.ui.form.ControlData {
	static trigger_change_on_input_event = false;
	make() {
		super.make();
		// $(this.label_area).addClass('pull-right');
		// $(this.disp_area).addClass('text-right');
	}
	make_input() {
		var me = this;
		super.make_input();
		this.$input
			// .addClass("text-right")
			.on("focus", function () {
				setTimeout(function () {
					if (!document.activeElement) return;
					document.activeElement.select();
				}, 100);
				return false;
			});
	}
	validate(value) {
		return this.parse(value);
	}
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
	}
	parse(value) {
		return cint(this.eval_expression(value), null);
	}
};

frappe.ui.form.ControlLongInt = frappe.ui.form.ControlInt;
