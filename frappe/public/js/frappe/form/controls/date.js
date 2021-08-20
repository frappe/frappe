frappe.ui.form.ControlDate = frappe.ui.form.ControlData.extend({
	trigger_change_on_input_event: false,
	make_input: function() {
		this._super();
		this.make_picker();
	},
	make_picker: function() {
		this.set_date_options();
		this.set_datepicker();
		this.set_t_for_today();
	},
	set_formatted_input: function(value) {
		this._super(value);
		if (this.timepicker_only) return;
		if (!this.datepicker) return;
		if (!value) {
			this.datepicker.clear();
			return;
		} else if (value === "Today") {
			value = this.get_now_date();
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

		let lang = 'en';
		frappe.boot.user && (lang = frappe.boot.user.language);
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
	update_datepicker_position: function() {
		if(!this.frm) return;
		// show datepicker above or below the input
		// based on scroll position
		// We have to bodge around the timepicker getting its position
		// wrong by 42px when opening upwards.
		const $header = $('.page-head');
		const header_bottom = $header.position().top + $header.outerHeight();
		const picker_height = this.datepicker.$datepicker.outerHeight() + 12;
		const picker_top = this.$input.offset().top - $(window).scrollTop() - picker_height;

		var position = 'top left';
		// 12 is the default datepicker.opts[offset]
		if (picker_top <= header_bottom) {
			position = 'bottom left';
			if (this.timepicker_only) this.datepicker.opts['offset'] = 12;
		} else {
			// To account for 42px incorrect positioning
			if (this.timepicker_only) this.datepicker.opts['offset'] = -30;
		}

		this.datepicker.update('position', position);
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
