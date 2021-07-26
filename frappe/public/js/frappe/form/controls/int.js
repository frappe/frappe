frappe.ui.form.ControlInt = frappe.ui.form.ControlData.extend({
	trigger_change_on_input_event: false,
	make: function () {
		this._super();
		// $(this.label_area).addClass('pull-right');
		// $(this.disp_area).addClass('text-right');
	},
	make_input: function () {
		var me = this;
<<<<<<< HEAD
		this._super();
		this.$input
			// .addClass("text-right")
			.on("focusout", function () {
				setTimeout(function () {
					if (!document.activeElement) return;
					document.activeElement.value
						= me.validate(document.activeElement.value);
				}, 100);
				return false;
			});
	},
	validate: function (value) {
=======
		super.make_input();
	}
	validate (value) {
>>>>>>> 52941e55b1 (fix: no need for focusout in favour of onchange)
		return this.parse(value);
	},
	eval_expression: function (value) {
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
	},
	parse: function (value) {
		return cint(this.eval_expression(value), null);
	}
});
