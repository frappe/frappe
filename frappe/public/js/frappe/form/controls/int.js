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
	eval_expression(value) {
		return typeof value === "string" ? frappe.utils.eval_expression(value) : value;
	}
	parse(value) {
		return cint(this.eval_expression(value), null);
	}
};

frappe.ui.form.ControlLongInt = frappe.ui.form.ControlInt;
