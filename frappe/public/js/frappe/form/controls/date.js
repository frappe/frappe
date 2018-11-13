

frappe.ui.form.ControlDate = frappe.ui.form.ControlData.extend({
	make_input: function() {
		this._super();
		this.set_date_options();
		this.set_datepicker();
		this.set_t_for_today();
	},
	set_formatted_input: function(value) {
		this._super(value);
		if (!this.datepicker) return;
		if(!value) {
			this.datepicker.clear();
			return;
		}

		let should_refresh = this.last_value && this.last_value !== value;

		if (!should_refresh) {
			if(this.datepicker.selectedDates.length > 0) {
				// if date is selected but different from value, refresh
				const selected_date =
					moment(this.datepicker.selectedDates[0])
						.format(this.date_format);

				should_refresh = selected_date !== value;
			} else {
				// if datepicker has no selected date, refresh
				should_refresh = true;
			}
		}

		if(should_refresh) {
			this.datepicker.selectDate(frappe.datetime.str_to_obj(value));
		}
	},
	set_date_options: function() {
		// webformTODO:
		let sysdefaults = frappe.boot.sysdefaults;

		let lang = frappe.boot.user.language || 'en';
		if(!$.fn.datepicker.language[lang]) {
			lang = 'en';
		}

		let date_format = sysdefaults && sysdefaults.date_format
			? sysdefaults.date_format : 'yyyy-mm-dd';

		let now_date = new Date();

		this.today_text = __("Today");
		this.date_format = frappe.defaultDateFormat;
		this.datepicker_options = {
			language: lang,
			autoClose: true,
			todayButton: true,
			dateFormat: date_format,
			startDate: now_date,
			keyboardNav: false,
			onSelect: () => {
				this.$input.trigger('change');
			},
			onShow: () => {
				this.datepicker.$datepicker
					.find('.datepicker--button:visible')
					.text(this.today_text);

				this.update_datepicker_position();
			}
		};
	},
	update_datepicker_position: function() {
		if(!this.frm) return;
		// show datepicker above or below the input
		// based on scroll position
		var window_height = $(window).height();
		var window_scroll_top = $(window).scrollTop();
		var el_offset_top = this.$input.offset().top + 280;
		var position = 'top left';
		if(window_height + window_scroll_top >= el_offset_top) {
			position = 'bottom left';
		}
		this.datepicker.update('position', position);
	},
	set_datepicker: function() {
		this.$input.datepicker(this.datepicker_options);
		this.datepicker = this.$input.data('datepicker');

		// today button didn't work as expected,
		// so explicitly bind the event
		this.datepicker.$datepicker
			.find('[data-action="today"]')
			.click(() => {
				this.datepicker.selectDate(this.get_now_date());
			});
	},
	get_now_date: function() {
		return frappe.datetime.now_date(true);
	},
	set_t_for_today: function() {
		var me = this;
		this.$input.on("keydown", function(e) {
			if(e.which===84) { // 84 === t
				if(me.df.fieldtype=='Date') {
					me.set_value(frappe.datetime.nowdate());
				} if(me.df.fieldtype=='Datetime') {
					me.set_value(frappe.datetime.now_datetime());
				} if(me.df.fieldtype=='Time') {
					me.set_value(frappe.datetime.now_time());
				}
				return false;
			}
		});
	},
	parse: function(value) {
		if(value) {
			return frappe.datetime.user_to_str(value);
		}
	},
	format_for_input: function(value) {
		if(value) {
			return frappe.datetime.str_to_user(value);
		}
		return "";
	},
	validate: function(value) {
		if(value && !frappe.datetime.validate(value)) {
			let sysdefaults = frappe.sys_defaults;
			let date_format = sysdefaults && sysdefaults.date_format
				? sysdefaults.date_format : 'yyyy-mm-dd';
			frappe.msgprint(__("Date {0} must be in format: {1}", [value, date_format]));
			return '';
		}
		return value;
	}
});
