frappe.ui.form.ControlCode = frappe.ui.form.ControlText.extend({
	make_input: function() {
		this._super();
		$(this.input_area).find("textarea")
			.allowTabs()
			.addClass('control-code');
	}
});
