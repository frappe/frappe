frappe.ui.form.ControlCurrency = frappe.ui.form.ControlFloat.extend({
	eval_expression: function(value) {
		if (typeof value === 'string' && value.includes(',')
			&& frappe.sys_defaults.number_format.startsWith("#.")) {
			return value;
		}

		if (typeof value === 'string' 
			&& value.match(/^[0-9+-/* ]+$/)) {
			if (value.includes(',')) {
				// paresFloat('1,44,000') returns 1.0
				// 1,44,000 are being passed when we paste rows from excel sheet to a table)

				const regex = new RegExp("\\,", "g");
				value = value.replace(regex, "");
			}

			try {
				return eval(value);
			} catch (e) {
				return value;
			}
		}

		// If not string
		return value;
	},

	format_for_input: function(value) {
		var formatted_value = format_number(parseFloat(value), this.get_number_format(), this.get_precision());
		return isNaN(parseFloat(value)) ? "" : formatted_value;
	},

	get_precision: function() {
		// always round based on field precision or currency's precision
		// this method is also called in this.parse()
		if (!this.df.precision) {
			if(frappe.boot.sysdefaults.currency_precision) {
				this.df.precision = frappe.boot.sysdefaults.currency_precision;
			} else {
				this.df.precision = get_number_format_info(this.get_number_format()).precision;
			}
		}

		return this.df.precision;
	}
});
