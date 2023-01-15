frappe.ui.form.ControlTime = class ControlTime extends frappe.ui.form.ControlDate {
	set_formatted_input(value) {
		super.set_formatted_input(value);
	}
	make_input() {
		this.timepicker_only = true;
		super.make_input();
	}
	make_picker() {
		//this.set_time_options();
		this.set_datepicker();
		this.refresh();
	}
	// set_time_options() {
	// 	let sysdefaults = frappe.boot.sysdefaults;

	// 	let time_format =
	// 		sysdefaults && sysdefaults.time_format ? sysdefaults.time_format : "HH:mm:ss";

	// 	this.time_format = frappe.defaultTimeFormat;
	// 	this.datepicker_options = {
	// 		language: "en",
	// 		timepicker: true,
	// 		onlyTimepicker: true,
	// 		timeFormat: time_format.toLowerCase().replace("mm", "ii"),
	// 		startDate: frappe.datetime.now_time(true),
	// 		onSelect: () => {
	// 			// ignore micro seconds
	// 			if (
	// 				moment(this.get_value(), time_format).format("HH:mm:ss") !=
	// 				moment(this.value, time_format).format("HH:mm:ss")
	// 			) {
	// 				this.$input.trigger("change");
	// 			}
	// 		},
	// 		onShow: () => {
	// 			$(".datepicker--button:visible").text(__("Now"));

	// 			this.update_datepicker_position();
	// 		},
	// 		keyboardNav: false,
	// 		todayButton: true,
	// 	};
	// }
	set_input(value) {
		super.set_input(value);
		// if (
		// 	value &&
		// 	((this.last_value && this.last_value !== this.value))
		// ) {
		// 	let time_format = frappe.sys_defaults.time_format || "HH:mm:ss";
		// 	var date_obj = frappe.datetime.moment_to_date_obj(moment(value, time_format));
		// 	this.datepicker.selectDate(date_obj);
		// }
	}
	set_datepicker() {
		let user_time_fmt = frappe.datetime.get_user_time_fmt();
		this.load_lib().then(() => {
			const customdate = require("./tempus-dominus/plugins/customDateFormat.js");
			tempusDominus.extend(customdate);
				new tempusDominus.TempusDominus(document.querySelector(`[data-fieldname="${this.df.fieldname}"]`), {
				display: {
					components: {
					decades: false,
					year: false,
					month: false,
					date: false,
					hours: true,
					minutes: true,
					seconds: user_time_fmt.endsWith("ss")
					},
					icons: {
						type: 'sprites',
						time: '#icon-select',
						date: '#icon-select',
						up: '#icon-small-up',
						down: '#icon-down',
						previous: '#icon-left',
						next: '#icon-right',
						today: '#icon-today',
						clear: '#icon-refresh',
						close: '#icon-close-alt'
					},
					theme: 'dark',
					buttons: {
						today: true,
						clear: true,
						close: false
					  }
				},
				localization: {
					locale: frappe.boot.user.language,
					hourCycle: 'h23',
					dateFormats: {
						L: user_time_fmt,
					  },
					format: 'L',
				  }
		  });
		});
		this.$input.attr("inputmode", "none");
	}
	set_description() {
		const { description } = this.df;
		const { time_zone } = frappe.sys_defaults;
		if (!frappe.datetime.is_system_time_zone()) {
			if (!description) {
				this.df.description = time_zone;
			} else if (!description.includes(time_zone)) {
				this.df.description += "<br>" + time_zone;
			}
		}
		super.set_description();
	}
	parse(value) {
		if (value) {
			if (value == "Invalid date") {
				value = "";
			}
			return frappe.datetime.user_to_str(value, true);
		}
	}
	format_for_input(value) {
		if (value) {
			return frappe.datetime.str_to_user(value, true);
		}
		return "";
	}
	validate(value) {
		// if (value && !frappe.datetime.validate(value)) {
		// 	let sysdefaults = frappe.sys_defaults;
		// 	let time_format =
		// 		sysdefaults && sysdefaults.time_format ? sysdefaults.time_format : "HH:mm:ss";
		// 	frappe.msgprint(__("Time {0} must be in format: {1}", [value, time_format]));
		// 	return "";
		// }
		return value;
	}

	load_lib() {
		return new Promise((resolve) => {
			var asset_dir = "/assets/frappe/js/lib/tempus-dominus/";
			frappe.require(
				[
					asset_dir + "tempus-dominus.css",
					asset_dir + "tempus-dominus.js",
					asset_dir + "popper.min.js",
				],
				resolve
			);
		});
	}
};
