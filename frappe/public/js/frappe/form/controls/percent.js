frappe.ui.form.ControlPercent = class ControlPercent extends frappe.ui.form.ControlFloat {
	format_for_input(value) {
		if (value === null || value === undefined || isNaN(Number(value))) {
			return "";
		}
		const precision = value.toString().split(".")[1]?.length || 0;
		return format_number(
			value,
			this.get_number_format(),
			Math.min(this.get_precision(), precision)
		);
	}
};
