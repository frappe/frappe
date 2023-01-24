frappe.ui.form.ControlTime = class ControlTime extends frappe.ui.form.ControlDate {
	set_formatted_input(value) {
		super.set_formatted_input(value);
	}
	make_input() {
		this.timepicker_only = true;
		super.make_input();
	}
	make_picker() {
		this.set_datepicker();
		this.refresh();
	}
	set_input(value) {
		super.set_input(value);
		if (
			value &&
			((this.last_value && this.last_value !== this.value) ||
				!this.datepicker.dates.picked.length)
		) {
			let time_format = frappe.sys_defaults.time_format || "HH:mm:ss";
			var date_obj = frappe.datetime.moment_to_date_obj(moment(value, time_format));
			this.datepicker.dates.parseInput(frappe.datetime.obj_to_str(date_obj));
		}
	}
	set_datepicker() {
		let user_time_fmt = frappe.datetime.get_user_time_fmt();
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
					year: false,
					month: false,
					date: false,
					hours: true,
					minutes: true,
					seconds: user_time_fmt.endsWith("ss"),
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
			defaultDate: frappe.model.get_value(this.doctype, this.docname, this.df.fieldname),
			localization: {
				locale: lang,
				hourCycle: "h23",
				format: user_time_fmt,
			},
		});
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
		if (value && !frappe.datetime.validate(value)) {
			let sysdefaults = frappe.sys_defaults;
			let time_format =
				sysdefaults && sysdefaults.time_format ? sysdefaults.time_format : "HH:mm:ss";
			frappe.msgprint(__("Time {0} must be in format: {1}", [value, time_format]));
			return "";
		}
		return value;
	}
};
