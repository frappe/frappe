frappe.ui.form.ControlAutocomplete = frappe.ui.form.ControlData.extend({
	make_input() {
		this._super();
		this.setup_awesomplete();
	},

	setup_awesomplete() {
		var me = this;

		this.awesomplete = new Awesomplete(this.input, {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: this.get_data(),
			data: function (item) {
				if (typeof item === 'string') {
					item = {
						label: item,
						value: item
					};
				}

				return {
					label: item.label || item.value,
					value: item.value
				};
			}
		});

		$(this.input_area).find('.awesomplete ul').css('min-width', '100%');

		this.$input.on('input', () => {
			this.awesomplete.list = this.get_data();
		});

		this.$input.on('focus', () => {
			if (!this.$input.val()) {
				this.$input.val('');
				this.$input.trigger('input');
			}
		});

		this.$input.on('awesomplete-selectcomplete', () => {
			this.$input.trigger('change');
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
