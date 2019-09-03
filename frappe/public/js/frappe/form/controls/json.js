frappe.ui.form.ControlJSON = frappe.ui.form.ControlCode.extend({
	set_language() {
		this.df.options = 'JSON';
		this._super();
	},
	set_formatted_input(value) {
		return this.load_lib().then(() => {
			if (!this.editor) return;
			if (value === this.get_input_value()) return;
			if (typeof value === 'object')
				value = JSON.stringify(value, undefined, 2);
			this.editor.session.setValue(value);
		});
	}
});
