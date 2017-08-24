frappe.ui.form.ControlFloat = frappe.ui.form.ControlInt.extend({
	parse: function(value) {
		return isNaN(parseFloat(value)) ? null : flt(value, this.get_precision());
	},

	format_for_input: function(value) {
		var number_format;
		if (this.df.fieldtype==="Float" && this.df.options && this.df.options.trim()) {
			number_format = this.get_number_format();
		}
		var formatted_value = format_number(parseFloat(value), number_format, this.get_precision());
		return isNaN(parseFloat(value)) ? "" : formatted_value;
	},

	// even a float field can be formatted based on currency format instead of float format
	get_number_format: function() {
		var currency = frappe.meta.get_field_currency(this.df, this.get_doc());
		return get_number_format(currency);
	},

	get_precision: function() {
		// round based on field precision or float precision, else don't round
		return this.df.precision || cint(frappe.boot.sysdefaults.float_precision, null);
	}
});

frappe.ui.form.ControlPercent = frappe.ui.form.ControlFloat;
