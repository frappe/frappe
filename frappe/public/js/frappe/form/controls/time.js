frappe.ui.form.ControlTime = frappe.ui.form.ControlData.extend({
	make_input: function() {
		var me = this;
		this._super();
		this.$input.datepicker({
			language: "en",
			timepicker: true,
			onlyTimepicker: true,
			timeFormat: "hh:ii:ss",
			startDate: frappe.datetime.now_time(true),
			onSelect: function() {
				// ignore micro seconds
				if (moment(me.get_value(), 'hh:mm:ss').format('HH:mm:ss') != moment(me.value, 'hh:mm:ss').format('HH:mm:ss')) {
					me.$input.trigger('change');
				}
			},
			onShow: function() {
				$('.datepicker--button:visible').text(__('Now'));
			},
			keyboardNav: false,
			todayButton: true
		});
		this.datepicker = this.$input.data('datepicker');
		this.datepicker.$datepicker
			.find('[data-action="today"]')
			.click(() => {
				this.datepicker.selectDate(frappe.datetime.now_time(true));
			});
		this.refresh();
	},
	set_input: function(value) {
		this._super(value);
		if(value
			&& ((this.last_value && this.last_value !== this.value)
				|| (!this.datepicker.selectedDates.length))) {

			var date_obj = frappe.datetime.moment_to_date_obj(moment(value, 'HH:mm:ss'));
			this.datepicker.selectDate(date_obj);
		}
	},
	set_description: function() {
		const { description } = this.df;
		const { time_zone } = frappe.sys_defaults;
		if (!frappe.datetime.is_timezone_same()) {
			if (!description) {
				this.df.description = time_zone;
			} else if (!description.includes(time_zone)) {
				this.df.description += '<br>' + time_zone;
			}
		}
		this._super();
	},
	parse: function(value) {
		if (value) {
			return frappe.datetime.user_to_str(value, true);
		}
	},
	format_for_input: function(value) {
		if (value) {
			return frappe.datetime.str_to_user(value, true);
		}
		return "";
	},
	validate: function(value) {
		if (value && !frappe.datetime.validate(value)) {
			let time_format = 'HH:mm:ss';
			frappe.msgprint(__("Time {0} must be in format: {1}", [value, time_format.bold()]));
			return '';
		}
		return value;
	}
});
