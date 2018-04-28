frappe.ui.form.ControlMultiSelect = frappe.ui.form.ControlAutocomplete.extend({
	get_awesomplete_settings() {
		const settings = this._super();

		return Object.assign(settings, {
			filter: function(text, input) {
				var d = this.get_item(text.value);
				if(!d) {
					return Awesomplete.FILTER_CONTAINS(text, input.match(/[^,]*$/)[0]);
				}
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

	get_values() {
		const value = this.get_value() || '';
		const values = value.split(/\s*,\s*/).filter(d => d);

		return values;
	},

	get_data() {
		let data;
		if(this.df.get_data) {
			data = this.df.get_data();
			this.set_data(data);
		} else {
			data = this._super();
		}
		const values = this.get_values() || [];

		// return values which are not already selected
		if(data) data.filter(d => !values.includes(d));
		return data;
	}
});
