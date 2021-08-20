import Awesomplete from 'awesomplete';

frappe.ui.form.ControlAutocomplete = frappe.ui.form.ControlData.extend({
	trigger_change_on_input_event: false,
	make_input() {
		this._super();
		this.setup_awesomplete();
		this.set_options();
	},

	set_options() {
		if (this.df.options) {
			let options = this.df.options || [];
			this._data = this.parse_options(options);
		}
	},

	get_awesomplete_settings() {
		var me = this;
		return {
			minChars: 0,
			maxItems: this.df.max_items || 99,
			autoFirst: true,
			list: this.get_data(),
			data: function(item) {
				if (!(item instanceof Object)) {
					var d = { value: item };
					item = d;
				}

				return {
					label: item.label || item.value,
					value: item.value
				};
			},
			filter: function(item, input) {
				let hay = item.label + item.value;
				return Awesomplete.FILTER_CONTAINS(hay, input);
			},
			item: function(item) {
				var d = this.get_item(item.value);
				if (!d) {
					d = item;
				}

				if (!d.label) {
					d.label = d.value;
				}

				var _label = me.translate_values ? __(d.label) : d.label;
				var html = '<strong>' + _label + '</strong>';
				if (d.description) {
					html += '<br><span class="small">' + __(d.description) + '</span>';
				}

				return $('<li></li>')
					.data('item.autocomplete', d)
					.prop('aria-selected', 'false')
					.html('<a><p>' + html + '</p></a>')
					.get(0);
			},
			sort: () => {
				return 0;
			}
		};
	},

	setup_awesomplete() {
		this.awesomplete = new Awesomplete(
			this.input,
			this.get_awesomplete_settings()
		);

		$(this.input_area)
			.find('.awesomplete ul')
			.css('min-width', '100%');

		this.$input.on(
			'input',
			frappe.utils.debounce(() => {
				this.awesomplete.list = this.get_data();
			}, 500)
		);

		this.$input.on('focus', () => {
			if (!this.$input.val()) {
				this.$input.val('');
				this.$input.trigger('input');
			}
		});

		this.$input.on("awesomplete-open", () => {
			this.autocomplete_open = true;
		});

		this.$input.on("awesomplete-close", () => {
			this.autocomplete_open = false;
		});

		this.$input.on('awesomplete-selectcomplete', () => {
			this.$input.trigger('change');
		});
	},

	validate(value) {
		if (this.df.ignore_validation) {
			return value || '';
		}
		let valid_values = this.awesomplete._list.map(d => d.value);
		if (!valid_values.length) {
			return value;
		}
		if (valid_values.includes(value)) {
			return value;
		} else {
			return '';
		}
	},

	parse_options(options) {
		if (typeof options === 'string') {
			options = options.split('\n');
		}
		if (typeof options[0] === 'string') {
			options = options.map(o => ({ label: o, value: o }));
		}
		return options;
	},

	get_data() {
		return this._data || [];
	},

	set_data(data) {
		data = this.parse_options(data);
		if (this.awesomplete) {
			this.awesomplete.list = data;
		}
		this._data = data;
	}
});
