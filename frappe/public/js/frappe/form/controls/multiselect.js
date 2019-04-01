import Awesomplete from 'awesomplete';

frappe.ui.form.ControlMultiSelect = frappe.ui.form.ControlAutocomplete.extend({
	make_input() {
		this._super();
		this.options_label = this.df.options && this.df.options.length && this.df.options[0].label;
		this.$input_area = $(this.input_area);
	},

	get_awesomplete_settings() {
		const settings = this._super();

		return Object.assign(settings, {
			filter: function(text, input) {
				let d = this.get_item(text.value);
				if(!d) {
					return Awesomplete.FILTER_CONTAINS(text, input.match(/[^,]*$/)[0]);
				}

				let getMatch = value => Awesomplete.FILTER_CONTAINS(value, input.match(/[^,]*$/)[0]);

				// match typed input with label or value or description
				let v = getMatch(d.label);
				if(!v && d.value) {
					v = getMatch(d.value);
				}
				if(!v && d.description) {
					v = getMatch(d.description);
				}

				return v;
			},

			replace: function(text) {
				const before = this.input.value.match(/^.+,\s*|/)[0];
				this.input.value = before + text + ", ";
			}
		});
	},

	get_value() {
		let data = this._super();
		if (!data) return;
		// find value of label from option list and return actual value string
		if (this.options_label) {
			data = data.map(val => {
				let option = this.df.options.find(op => op.label === val);
				return option ? option.value : null;
			}).filter(Boolean);
		}
		return data;
	},

	validate(value) {
		if (!value) return;
		let values;

		if (typeof value === 'string') {
			value = value.trim().replace(/\,$/, '');
			if (this.df.tags) {
				values = this.value ? this.value : [];
				values.push(value);
			} else {
				values = this.get_array_from_string_of_values(value);
			}
		} else {
			values = value;
		}
		return values;
	},

	set_formatted_input(value) {
		if (!value) return;
		// find label of value from option list and set from it as input
		if (this.options_label) {
			value = value.map(val => {
				let option = this.df.options.find(op => op.value === val);
				return option ? option.label : val;
			}).filter(Boolean);
		}

		if(this.df.tags) {
			this.set_pill_html(value);
			this._super('');
		} else {
			value = value.join(', ');
			this._super(value);
		}
	},

	get_data() {
		let data;
		if(this.df.get_data) {
			data = this.df.get_data();
			this.set_data(data);
		} else {
			data = this._super();
		}
		const values = this.get_value() || [];

		// return values which are not already selected
		if(data) data.filter(d => !values.includes(d));
		return data;
	},

	set_pill_html(values) {
		const html = values
			.map(value => this.get_pill_html(value))
			.join('');

		this.$input_area.find('.tb-selected-value').remove();
		this.$input_area.prepend(html);
	},

	get_pill_html(value) {
		const encoded_value = encodeURIComponent(value);
		return `<div class="btn-group tb-selected-value" data-value="${encoded_value}">
			<button class="btn btn-default btn-xs btn-link-to-form">${__(value)}</button>
			<button class="btn btn-default btn-xs btn-remove">
				<i class="fa fa-remove text-muted"></i>
			</button>
		</div>`;
	},

	get_array_from_string_of_values(value) {
		return value ? value.split(',').map(d => d.trim()) : [];
	}
});
