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
	parse: function(value) {
		return cint(value, null);
	}
});
