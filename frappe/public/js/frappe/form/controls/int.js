frappe.ui.form.ControlInt = frappe.ui.form.ControlData.extend({
	make: function() {
		this._super();
		// $(this.label_area).addClass('pull-right');
		// $(this.disp_area).addClass('text-right');
	},
	make_input: function() {
		var me = this;
		this._super();
		this.$input
			// .addClass("text-right")
			.on("focus", function() {
				setTimeout(function() {
					if(!document.activeElement) return;
					document.activeElement.value
						= me.validate(document.activeElement.value);
					document.activeElement.select();
				}, 100);
				return false;
			});
	},
	eval_expression: function(value) {
		if (typeof value==='string'
			&& value.match(/^[0-9+-/* ]+$/)
			// strings with commas are evaluated incorrectly
			// for e.g 47,186.00 -> 186
			&& !value.includes(',')) {
			try {
				return eval(value);
			} catch (e) {
				// bad expression
				return value;
			}
		} else {
			return value;
		}
	},
	parse: function(value) {
		return cint(this.eval_expression(value), null);
	}
});
