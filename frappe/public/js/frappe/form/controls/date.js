frappe.ui.form.ControlDate = frappe.ui.form.ControlData.extend({
	make_input: function() {
		this._super();
		this.set_date_options();
		this.set_datepicker();
		this.set_t_for_today();
	},

	set_formatted_input: function(value) {
		this._super(value);
		if(!value) return;

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
		var me = this;
		var lang = frappe.boot.user.language;
		if(!$.fn.datepicker.language[lang]) {
			lang = 'en';
		}
		this.today_text = __("Today");
		this.date_format = moment.defaultDateFormat;
		this.datepicker_options = {
			language: lang,
			autoClose: true,
			todayButton: true,
			dateFormat: (frappe.boot.sysdefaults.date_format || 'yyyy-mm-dd'),
			startDate: frappe.datetime.now_date(true),
			keyboardNav: false,

			onSelect: () => {
				this.$input.trigger('change');
			},
			onShow: () => {
				this.datepicker.$datepicker
					.find('.datepicker--button:visible')
					.text(me.today_text);

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

		// setup timeformat.
		// Okay, for some reason I am unable to get the context for datepicker anywhere beyond this scope.
		// Hence, adding it here. Also, datepicker seems to be a bit buggy. - Achilles <achilles@frappe.io>

		// Helper function.
		const get_timepicker_options = function (timepicker, format) {
			const options = { }

			if ( format == 12 ) {
				// AM - PM.
				if ( timepicker.hours > 12 ) {
					options.hours  = timepicker.hours - 12;
					options.period = 'PM';
				} else {
					options.hours  = timepicker.hours == 0 ? 12 : timepicker.hours;
					options.period = 'AM';
				}
			} else {
				options.hours = timepicker.hours;
			}

			return options;
		}

		const datepicker  = this.datepicker;
		// Set it up here, not at datetime.js, because we're initializing it here.
		const options     = this.datepicker_options; // magic of the class attribute, I don't know where the fuck this get's initialised.
		if ( options.timepicker ) {
			const  timepicker = datepicker.timepicker;
			const $timepicker = timepicker.$timepicker;
			var   $format     = $timepicker.find('input[name="format"]');
			var   $ampm		  = $timepicker.find('.datepicker--time-current-ampm');
			
			// Set DOMs, these things don't build after datetime_options change.
			if ( !$format.length ) {
				$timepicker.find('.datepicker--time-sliders').append(`
					<div class="datepicker--time-row">
						<input name="format" type="range" value="0" min="0" max="1" step="1"/>
					</div>
				`)
			}
			$format = $timepicker.find('input[name="format"]');

			if ( !$ampm.length ) {
				$timepicker.find('.datepicker--time-current')
							.append('<span class="datepicker--time-current-ampm"/>');
			}
			$ampm   = $timepicker.find('.datepicker--time-current-ampm');
			$ampm.hide();

			// Trigger AM PM
			$format.change(function ( ) {
				// BRUTAL HACK! SO BRUTAL.
				// The thing is, the $ampm DOM from timepicker is not set, raising an undefined.
				// We'll to this shit manually.
				var   options = { }
				const value   = $(this).val();

				if ( value == 1 ) {
					options   = get_timepicker_options(timepicker, 12);
					$ampm.html(options.period);
					$ampm.show();
				} else {
					// 24 Hours.
					options   = get_timepicker_options(timepicker, 24);
					$ampm.hide();
				}

				timepicker.$hours.val(timepicker.hours); // always be 24-hour.
				timepicker.$hoursText.html(`${parseInt(options.hours) < 10 ? '0' : ''}${options.hours}`);
				
				// Also, when it changes.
				timepicker.$hours.on('input change', function ( ) {
					if ( value == 1 ) {
						options = get_timepicker_options(timepicker, 12);
						$ampm.html(options.period);
					} else {
						options = get_timepicker_options(timepicker, 24);
					}

					timepicker.$hoursText.html(`${parseInt(options.hours) < 10 ? '0' : ''}${options.hours}`);
				});
			});
		}
		// end setup timeformat
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
			frappe.msgprint(__("Date must be in format: {0}", [frappe.sys_defaults.date_format || "yyyy-mm-dd"]));
			return '';
		}
		return value;
	}
});