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

	get_values() {
		const value = this.get_value() || '';
		const values = value.split(/\s*,\s*/).filter(d => d);

		return values;
	},

	get_data() {
		const values = this.get_values();
		const data = this._super();

		// return values which are not already selected
		return data.filter(d => !values.includes(d));
	},
	get_options() {
		let options = '';
		if(this.df.get_options) {
			options = this.df.get_options();
		}
		else if (this.docname==null && cur_dialog) {
			//for dialog box
			options = cur_dialog.get_value(this.df.options);
		}
		else if (!cur_frm) {
			const selector = `input[data-fieldname="${this.df.options}"]`;
			let input = null;
			if (cur_list) {
				// for list page
				input = cur_list.wrapper.find(selector);
			}
			if (cur_page) {
				input = $(cur_page.page).find(selector);
			}
			if (input) {
				options = input.val();
			}
		}

		return options;
	},
});
