frappe.ui.form.ControlMultiSelect = frappe.ui.form.ControlAutocomplete.extend({
	get_awesomplete_settings() {
		const settings = this._super();

		return Object.assign(settings, {
			filter: function(text, input) {
				var d = this.get_item(text.value);
				var v = Awesomplete.FILTER_CONTAINS(d.label, input.match(/[^,]*$/)[0]);
				if(!v && d.value){
					v = Awesomplete.FILTER_CONTAINS(d.value, input.match(/[^,]*$/)[0]);
				}
				if(!v && d.description){
					v = Awesomplete.FILTER_CONTAINS(d.description, input.match(/[^,]*$/)[0]);
				}
				return v;
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
