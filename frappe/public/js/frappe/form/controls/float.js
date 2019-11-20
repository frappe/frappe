frappe.ui.form.ControlFloat = frappe.ui.form.ControlInt.extend({
	parse: function(value) {
		value = this.eval_expression(value);
		return isNaN(parseFloat(value)) ? null : flt(value, this.get_precision(), 
			// While parsing currency, get_number_format passes currency's number_format
			// In case of parsing float, it passes global number_format
			this.get_number_format());
	},

	format_for_input: function(value) {
		var number_format;
		if (this.df.fieldtype==="Float" && this.df.options && this.df.options.trim()) {
			number_format = this.get_number_format();
		}
		var formatted_value = format_number(parseFloat(value), number_format, this.get_precision());
		return isNaN(parseFloat(value)) ? "" : formatted_value;
	},

	get_number_format: function() {
		// In case of 'Float' field currency's number_format shouldn't be used for formatting
		return get_number_format();
	},

	get_precision: function() {
		// round based on field precision or float precision, else don't round
		return this.df.precision || cint(frappe.boot.sysdefaults.float_precision, null);
	}
});

frappe.ui.form.ControlPercent = frappe.ui.form.ControlFloat;
