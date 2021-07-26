frappe.ui.form.ControlInt = class ControlInt extends frappe.ui.form.ControlData {
	static trigger_change_on_input_event = false
	make () {
		super.make();
		// $(this.label_area).addClass('pull-right');
		// $(this.disp_area).addClass('text-right');
	}
	make_input () {
		var me = this;
		super.make_input();
	}
	validate (value) {
		return this.parse(value);
	}
	eval_expression (value) {
		if (typeof value === 'string') {
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
	parse (value) {
		return cint(this.eval_expression(value), null);
	}
};
