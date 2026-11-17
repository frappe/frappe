frappe.ui.form.ControlCurrency = class ControlCurrency extends frappe.ui.form.ControlFloat {
	get_precision() {
		// always round based on field precision or currency's precision
		// this method is also called in this.parse()
		if (typeof this.df.precision == "number" || this.df.precision) {
			return this.df.precision;
		}

		return (
			frappe.boot.sysdefaults.currency_precision ||
			get_number_format_info(this.get_number_format()).precision
		);
	}
};
