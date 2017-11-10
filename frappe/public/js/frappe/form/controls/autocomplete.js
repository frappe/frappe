frappe.ui.form.ControlAutocomplete = frappe.ui.form.ControlData.extend({
	make_input() {
		this._super();
		this.setup_awesomplete();
		this.set_options();
	},

	set_options() {
		if (this.df.options) {
			let options = this.df.options || [];
			if(typeof options === 'string') {
				options = options.split('\n');
			}
			this._data = options;
		}
	},

	get_awesomplete_settings() {
		return {
			minChars: 0,
			maxItems: 99,
			autoFirst: true,
			list: this.get_data()
		};
	},

	setup_awesomplete() {
		var me = this;

		this.awesomplete = new Awesomplete(this.input, this.get_awesomplete_settings());

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
