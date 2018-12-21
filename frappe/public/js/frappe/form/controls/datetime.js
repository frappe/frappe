frappe.ui.form.ControlDatetime = frappe.ui.form.ControlDate.extend({
	set_date_options: function() {
		this._super();
		this.today_text = __("Now");
		let sysdefaults = frappe.boot.sysdefaults;
		this.date_format = frappe.defaultDatetimeFormat;
		let time_format = sysdefaults && sysdefaults.time_format
			? sysdefaults.time_format : 'HH:mm:ss';
		$.extend(this.datepicker_options, {
			timepicker: true,
			timeFormat: time_format.toLowerCase().replace("mm", "ii")
		});
	},
	get_now_date: function() {
		return frappe.datetime.now_datetime(true);
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
	set_datepicker: function() {
		this._super();
		if (this.datepicker.opts.timeFormat.indexOf('s') == -1) {
			// No seconds in time format
			this.noSeconds = true;
			const $tp = this.datepicker.timepicker;
			$tp.$seconds.parent().css('display', 'none');
			$tp.$secondsText.css('display', 'none');
			$tp.$secondsText.prev().css('display', 'none');
		} else {
			this.noSeconds = false;
		}
	},
	update_datepicker_position: function() {
		if(!this.frm) return;
		// show datepicker above or below the input
		// based on scroll position
		const scroll_limit = $(window).scrollTop() + $(window).height()
		const picker_bottom = this.$input.offset().top + this.$input.outerHeight() + 12 + this.datepicker.$datepicker.outerHeight()

		var position = 'bottom left';
		//if (picker_top > scroll_limit + window_scroll) {
		if (picker_bottom >= scroll_limit) {
			position = 'top left';
			// bodge around the picker being 30 pixels shorter than
			// it should be due to hiding seconds
			if (this.noSeconds) this.datepicker.opts['offset'] = -28;
		} else {
			if (this.noSeconds) this.datepicker.opts['offset'] = 12;
		}
		this.datepicker.update('position', position);
	},
});
