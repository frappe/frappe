frappe.ui.form.ControlMultiSelect = frappe.ui.form.ControlAutocomplete.extend({
	get_awesomplete_settings() {
		const settings = this._super();

		return Object.assign(settings, {
			filter: function(text, input) {
				return Awesomplete.FILTER_CONTAINS(text, input.match(/[^,]*$/)[0]);
			},

			item: function(text, input) {
				return Awesomplete.ITEM(text, input.match(/[^,]*$/)[0]);
			},

			replace: function(text) {
				const before = this.input.value.match(/^.+,\s*|/)[0];
				this.input.value = before + text + ", ";
			}
		});
	},

	get_data() {
		const value = this.get_value() || '';
		const values = value.split(', ').filter(d => d);
		const data = this._super();

		// return values which are not already selected
		return data.filter(d => !values.includes(d));
	}
});
