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
					document.activeElement.value = me.validate(document.activeElement.value);
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
			if (value.match(/^[0-9+\-/* ]+$/)) {
				// If it is a string containing operators
				try {
					return eval(value);
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
