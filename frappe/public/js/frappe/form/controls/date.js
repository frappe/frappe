frappe.ui.form.ControlDate = class ControlDate extends frappe.ui.form.ControlData {
	static trigger_change_on_input_event = false;
	make_input() {
		super.make_input();
		this.make_picker();
	}
	make_picker() {
		this.set_datepicker();
		this.set_t_for_today();
	}
	set_formatted_input(value) {
		//Datepicker does not recognize 3 digit year values. If user mistypes, current year will be taken instead.
		if (value) {
			if (value.startsWith("0")) {
				value = value.substring(4);
				value = moment().year() + value;
			}
		}

		if (value === "Today") {
			value = this.get_now_date();
		}

		super.set_formatted_input(value);
		if (this.timepicker_only) return;
		if (!this.datepicker) return;
		if (!value) {
			this.datepicker.clear();
			return;
		}

		let should_refresh = this.last_value && this.last_value !== value;
		if (!should_refresh) {
			if (this.datepicker.dates.picked.length > 0) {
				// if date is selected but different from value, refresh
				const selected_date = moment(this.datepicker.dates.picked[0]).format(
					this.date_format
				);

				should_refresh = selected_date !== value;
			} else {
				//if datepicker has no selected date, refresh
				should_refresh = true;
			}
		}

		if (should_refresh) {
			this.datepicker.dates.parseInput(frappe.datetime.str_to_user(value));
		}
	}

	get_start_date() {
		return this.get_now_date();
	}

	set_datepicker() {
		let date_value = frappe.datetime.str_to_user(
			frappe.model.get_value(this.doctype, this.docname, this.df.fieldname)
		);
		if (!date_value) {
			date_value = undefined;
		}
		let user_fmt = frappe.datetime.get_user_date_fmt().replace("mm", "MM");

		let first_day = frappe.datetime.get_first_day_of_the_week_index();

		let lang = "en";
		frappe.boot.user && (lang = frappe.boot.user.language);

		//Tempus-Dominus needs to have a unique query, therefore a unique ID is generated
		let id = this.doctype + this.df.fieldname + this.df.fieldtype + Date.now();
		this.$input.attr("inputmode", "none");
		this.$input.attr("id", id);
		let query_attr = document.getElementById(id);

		const tempusDominus = require("@eonasdan/tempus-dominus/dist/js/tempus-dominus.min.js");
		const customdate = require("@eonasdan/tempus-dominus/dist/plugins/customDateFormat.js");
		tempusDominus.extend(customdate);
		this.datepicker = new tempusDominus.TempusDominus(query_attr, {
			display: {
				components: {
					decades: false,
					year: true,
					month: true,
					date: true,
					hours: false,
					minutes: false,
					seconds: false,
				},
				icons: {
					type: "icons",
					time: "fa fa-clock-o",
					date: "fa fa-calendar",
					up: "fa fa-angle-up",
					down: "fa fa-angle-down",
					previous: "fa fa-chevron-left",
					next: "fa fa-chevron-right",
					today: "fa fa-calendar-times-o",
					clear: "fa fa-trash",
					close: "fa fa-xmark",
				},
				theme: "dark",
				buttons: {
					today: true,
					clear: true,
					close: false,
				},
			},
			defaultDate: date_value,
			localization: {
				locale: lang,
				startOfTheWeek: first_day,
				hourCycle: "h23",
				format: user_fmt,
			},
		});
	}
	update_datepicker_position() {
		if (!this.frm) return;
		// show datepicker above or below the input
		// based on scroll position
		// We have to bodge around the timepicker getting its position
		// wrong by 42px when opening upwards.
		const $header = $(".page-head");
		const header_bottom = $header.position().top + $header.outerHeight();
		const picker_height = this.datepicker.$datepicker.outerHeight() + 12;
		const picker_top = this.$input.offset().top - $(window).scrollTop() - picker_height;

		var position = "top left";
		// 12 is the default datepicker.opts[offset]
		if (picker_top <= header_bottom) {
			position = "bottom left";
			if (this.timepicker_only) this.datepicker.opts["offset"] = 12;
		} else {
			// To account for 42px incorrect positioning
			if (this.timepicker_only) this.datepicker.opts["offset"] = -30;
		}

		this.datepicker.update("position", position);
	}
	get_now_date() {
		return frappe.datetime
			.convert_to_system_tz(frappe.datetime.now_date(true), false)
			.toDate();
	}
	set_t_for_today() {
		var me = this;
		this.$input.on("keydown", function (e) {
			if (e.which === 84) {
				// 84 === t
				if (me.df.fieldtype == "Date") {
					me.set_value(frappe.datetime.nowdate());
				}
				if (me.df.fieldtype == "Datetime") {
					me.set_value(frappe.datetime.now_datetime());
				}
				if (me.df.fieldtype == "Time") {
					me.set_value(frappe.datetime.now_time());
				}
				return false;
			}
		});
	}
	parse(value) {
		if (value) {
			if (value == "Invalid date") {
				return "";
			}
			return frappe.datetime.user_to_str(value, false, true);
		}
	}
	format_for_input(value) {
		if (value) {
			return frappe.datetime.str_to_user(value, false, true);
		}
		return "";
	}
	validate(value) {
		if (value && !frappe.datetime.validate(value)) {
			let sysdefaults = frappe.sys_defaults;
			let date_format =
				sysdefaults && sysdefaults.date_format ? sysdefaults.date_format : "yyyy-mm-dd";
			frappe.msgprint(__("Date {0} must be in format: {1}", [value, date_format]));
			return "";
		}
		return value;
	}
	get_df_options() {
		let df_options = this.df.options;
		if (!df_options) return {};

		let options = {};
		if (typeof df_options === "string") {
			try {
				options = JSON.parse(df_options);
			} catch (error) {
				console.warn(`Invalid JSON in options of "${this.df.fieldname}"`);
			}
		} else if (typeof df_options === "object") {
			options = df_options;
		}
		return options;
	}
};
