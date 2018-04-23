frappe.ui.form.ControlAutocomplete = frappe.ui.form.ControlData.extend({
	make_input() {
		this._super();
		this.setup_awesomplete();
		this.set_options();
	},

	set_options() {
		if (this.df.options) {
			let options = this.df.options || [];
			if (typeof options === 'string') {
				options = options.split('\n');
			}
			if (typeof options[0] === 'string') {
				options = options.map(o => ({label: o, value: o}));
			}
			this._data = options;
		}
	},

	get_options() {
		return this.df.options;
	},

	get_awesomplete_settings() {
		var me = this;
		return {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: this.get_data(),
			data: function (item) {
				return {
					label: item.label || item.value,
					value: item.value
				};
			},
			filter: function() {
				return true;
			},
			item: function (item) {
				var d = this.get_item(item.value);
				if(!d.label) {	d.label = d.value; }

				var _label = (me.translate_values) ? __(d.label) : d.label;
				var html = "<strong>" + _label + "</strong>";
				if(d.description && d.value!==d.description) {
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
		this.awesomplete = new Awesomplete(this.input, this.get_awesomplete_settings());

		$(this.input_area).find('.awesomplete ul').css('min-width', '100%');

		this.$input.on('input', () => {
			this.awesomplete.list = this.get_data();
		});

		this.$input.on('focus', () => {
			this.get_dropdown();
			if (!this.$input.val()) {
				this.$input.val('');
				this.$input.trigger('input');
			}
		});

		this.$input.on('input', () => {
			this.get_dropdown();
		});

		this.$input.on('awesomplete-selectcomplete', () => {
			this.$input.trigger('change');
		});
	},

	get_dropdown() {
		var me = this;
		const value = this.get_value() || '';
		const values = value.split(', ').filter(d => d);
		var term = values.pop() || '';
		var args = {
			'txt': term,
			'doctype': this.get_options()
		};

		frappe.call({
			type: "GET",
			method:'frappe.desk.search.search_link',
			no_spinner: true,
			args: args,
			callback: function(r) {
				me._data = r.results
			}
		});
	},

	get_data() {
		return this._data || [];
	},

	set_data(data) {
		if (this.awesomplete) {
			this.awesomplete.list = data;
		}
		this._data = data;
	}
});
