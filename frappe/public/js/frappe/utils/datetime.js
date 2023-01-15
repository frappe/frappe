// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
import { parse, format, isMatch, startOfMonth, startOfWeek, startOfQuarter, startOfYear, endOfDay, endOfWeek, endOfMonth, endOfQuarter, endOfYear } from 'date-fns'
// import parse from 'date-fns/parse';
// import format from 'date-fns/format';
// import startOfMonth from 'date-fns/startOfMonth';
// import { toDate } from 'date-fns-tz'
// import { format as formattz } from 'date-fns-tz'
import { utcToZonedTime, zonedTimeToUtc, formatInTimeZone } from 'date-fns-tz'

frappe.provide("frappe.datetime");

frappe.defaultDateFormat = "yyyy-MM-dd";
frappe.defaultTimeFormat = "HH:mm:ss";
frappe.defaultDatetimeFormat = frappe.defaultDateFormat + " " + frappe.defaultTimeFormat;

frappe.provide("frappe.datetime");

$.extend(frappe.datetime, {
	convert_to_user_tz: function (date, format) {
		// format defaults to true
		// Converts the datetime string to system time zone first since the database only stores datetime in
		// system time zone and then convert the string to user time zone(from User doctype).

		var sys_time = null
		var usr_time = "";

		if (typeof date === 'string' && date.includes("-") && date.includes(" ") && date.includes(":")) {
			sys_time = zonedTimeToUtc(date, frappe.boot.time_zone.system);
			usr_time = formatInTimeZone(sys_time, frappe.boot.time_zone.user, frappe.defaultDatetimeFormat);
		}

		let usr_time_obj = parse(usr_time, frappe.defaultDatetimeFormat, new Date());
		return format === false ? usr_time_obj : usr_time;

	},

	convert_to_system_tz: function (date, format) {
		// format defaults to true
		// Converts the datetime string to user time zone (from User doctype) first since this fn is called in datetime which accepts datetime
		// in user time zone then convert the string to user time zone.
		// This is done so that only one timezone is present in database and we do not end up storing local timezone since it changes
		// as per the location of user.


		var usr_time = null;
		var sys_time = "";

		if (typeof date === 'string' && (date.includes("-") || date.includes(":"))) {
			usr_time = zonedTimeToUtc(date, frappe.boot.time_zone.user);
			sys_time = formatInTimeZone(usr_time, frappe.boot.time_zone.system, frappe.defaultDatetimeFormat);
		}

		let sys_time_obj = parse(sys_time, frappe.defaultDatetimeFormat, new Date());

		return format === false ? sys_time_obj : sys_time;

	},

	is_system_time_zone: function () {
		const getOffset = (timeZone = 'UTC', date = new Date()) => {
			const utcDate = new Date(date.toLocaleString('en-US', { timeZone: 'UTC' }));
			const tzDate = new Date(date.toLocaleString('en-US', { timeZone }));
			return (tzDate.getTime() - utcDate.getTime()) / 6e4;
		  }

		if (frappe.boot.time_zone && frappe.boot.time_zone.system && frappe.boot.time_zone.user) {
			return (
				getOffset(frappe.boot.time_zone.system) ===
				getOffset(frappe.boot.time_zone.user)
			);
		}

		return true;
	},

	is_timezone_same: function () {
		return frappe.datetime.is_system_time_zone();
	},

	str_to_obj: function (d) {
		return parse(d, frappe.defaultDatetimeFormat, new Date());
	},

	obj_to_str: function (d) {
		return d.toLocaleString("en-US")
	},

	obj_to_user: function (d) {
		return format(d, frappe.datetime.get_user_date_fmt().replace("mm", "MM"))
	},

	get_diff: function (d1, d2) {
		const day1 = parse(d1, frappe.defaultDatetFormat, new Date());
		const day2 = parse(d2, frappe.defaultDatetFormat, new Date());
		return Math.ceil((day1 - day2) / 1000 / 60 / 60 / 24);
	},

	get_hour_diff: function (d1, d2) {
		const day1 = parse(d1, frappe.defaultDatetFormat, new Date());
		const day2 = parse(d2, frappe.defaultDatetFormat, new Date());
		return Math.ceil((day1 - day2) / 1000 / 60 / 60);
	},

	get_day_diff: function (d1, d2) {
		const day1 = parse(d1, frappe.defaultDatetFormat, new Date());
		const day2 = parse(d2, frappe.defaultDatetFormat, new Date());
		return Math.ceil((day1 - day2) / 1000 / 60 / 60 / 24);
	},

	add_days: function (d, days) {
		const date = parse(d, frappe.defaultDatetFormat, new Date());
		return format(date.setDate(date.getDate() + days), frappe.defaultDateFormat);
	},

	add_months: function (d, months) {
		const date = parse(d, frappe.defaultDatetFormat, new Date());
		return format(date.setMonth(date.getMonth() + months), frappe.defaultDateFormat);
	},

	week_start: function () {
		return format(startOfWeek(new Date()), frappe.defaultDateFormat);
	},

	week_end: function () {
		return format(endOfWeek(new Date()), frappe.defaultDateFormat);
	},

	month_start: function () {
		return format(startOfMonth(new Date()), frappe.defaultDateFormat);
	},

	month_end: function () {
		return format(endOfMonth(new Date()), frappe.defaultDateFormat);
	},

	quarter_start: function () {
		return format(startOfQuarter(new Date()), frappe.defaultDateFormat);
	},

	quarter_end: function () {
		return format(endOfQuarter(new Date()), frappe.defaultDateFormat);
	},

	year_start: function () {
		return format(startOfYear(new Date()), frappe.defaultDateFormat);
	},

	year_end: function () {
		return format(endOfYear(new Date()), frappe.defaultDateFormat);
	},

	get_user_time_fmt: function () {
		return (frappe.sys_defaults && frappe.sys_defaults.time_format) || "HH:mm:ss";
	},

	get_user_date_fmt: function () {
		return (frappe.sys_defaults && frappe.sys_defaults.date_format) || "yyyy-mm-dd";
	},

	get_user_fmt: function () {
		// For backwards compatibility only
		return (frappe.sys_defaults && frappe.sys_defaults.date_format) || "yyyy-mm-dd";
	},

	str_to_user: function (val, only_time = false, only_date = false) {
		if (!val) return "";
		const user_date_fmt = frappe.datetime.get_user_date_fmt().replace("mm", "MM");
		const user_time_fmt = frappe.datetime.get_user_time_fmt();
		let user_format = user_time_fmt;
		let time_in = null;

		try {
			if (only_time) {
				time_in = parse(val, frappe.defaultTimeFormat, new Date());
			} else if (only_date) {

				time_in = parse(val, frappe.defaultDateFormat, new Date());
				user_format = user_date_fmt;
			} else {
				if (typeof val !== "string" || val.indexOf(" ") === -1) {
					time_in = parse(val, frappe.defaultDateFormat, new Date());
					user_format = user_date_fmt;
				} else {
					time_in = parse(val, frappe.defaultDatetimeFormat, new Date());
					user_format = user_date_fmt + " " + user_time_fmt;
				}

			}

			return format(time_in, user_format);
		}
		catch(e) {
			return "";
		}
	},

	user_to_str: function (val, only_time = false) {
		let user_time_fmt = frappe.datetime.get_user_time_fmt();
		let time_out = null
		let time_in = null

		let user_fmt = frappe.datetime.get_user_date_fmt().replace("mm", "MM");
		let system_fmt = "yyyy-MM-dd";


		if (only_time) {
			try {
				time_in = parse(val, frappe.defaultTimeFormat, new Date())
				time_out = format(time_in, frappe.defaultTimeFormat);
			}
			catch(e) {
				time_in = parse(val, user_time_fmt, new Date())
				time_out = format(time_in, frappe.defaultTimeFormat);
			}

			return time_out;
		}
		
		if (val.indexOf(" ") !== -1) {
			user_fmt += " " + user_time_fmt;
			system_fmt += " HH:mm:ss";
		}

		try {
			time_in = parse(val, system_fmt, new Date())
			time_out = format(time_in, system_fmt);
		}
		catch(e) {
			time_in = parse(val, user_fmt, new Date())
			time_out = format(time_in, system_fmt);
		}

		return time_out;
	},

	parse_to_datepicker: function(val) {
		let user_fmt = frappe.datetime.get_user_date_fmt().replace("mm", "MM");
		let user_fmt2 = frappe.datetime.get_user_date_fmt().replace("mm", "MM");
		let user_time_fmt = frappe.datetime.get_user_time_fmt();
		let system_fmt = "YYYY-MM-DD";

		if (val.indexOf(":") !== -1) {
			user_fmt2 = user_time_fmt;
			system_fmt += " HH:mm:ss";
			if (val.indexOf(" ") !== -1) {
				user_fmt2 = user_fmt + " " + user_time_fmt;
			}
		}
		let datepicker_out = parse(val, user_fmt2, new Date());
		return datepicker_out;
	},

	user_to_obj: function (d) {
		return frappe.datetime.str_to_obj(frappe.datetime.user_to_str(d));
	},

	global_date_format: function (d) {
		let time_in = null;
		let time_out = null;

		if (isMatch(d, frappe.defaultTimeFormat)) {
			time_in = parse(d, frappe.defaultTimeFormat, new Date())
			time_out = format(time_in, "do MMMM yyyy");
		}
		else {
			time_in = parse(d, frappe.defaultdateTimeFormat, new Date())
			time_out = format(time_in, "do MMMM yyyy, h:mm a");
		}
		
		return time_out;		
	},

	now_date: function (as_obj = false) {
		return frappe.datetime._date(frappe.defaultDateFormat, as_obj);
	},

	now_time: function (as_obj = false) {
		return frappe.datetime._date(frappe.defaultTimeFormat, as_obj);
	},

	now_datetime: function (as_obj = false) {
		return frappe.datetime._date(frappe.defaultDatetimeFormat, as_obj);
	},

	system_datetime: function (as_obj = false) {
		return frappe.datetime._date(frappe.defaultDatetimeFormat, as_obj, true);
	},

	_date: function (format, as_obj = false, system_time = false) {
		let time_zone = frappe.boot.time_zone?.system || frappe.sys_defaults.time_zone;

		// Whenever we are getting now_date/datetime, always make sure dates are fetched using user time zone.
		// This is to make sure that time is as per user time zone set in User doctype, If a user had to change the timezone,
		// we will end up having multiple timezone by not honouring timezone in User doctype.
		// This will make sure that at any point we know which timezone the user if following and not have random timezone
		// when the timezone of the local machine changes.
		if (!system_time) {
			time_zone = frappe.boot.time_zone?.user || time_zone;
		}

		usr_time = zonedTimeToUtc(new Date(), frappe.boot.time_zone.system);
		return formatInTimeZone(usr_time, time_zone, format);

	},

	nowdate: function () {
		return frappe.datetime.now_date();
	},

	get_today: function () {
		return frappe.datetime.now_date();
	},

	get_time: (timestamp) => {
		// return time with AM/PM
		const time_in = parse(d, frappe.defaultDatetimeFormat, new Date())
		return format(time_in, "h:mm a");
	},

	validate: function (d) {
		try {
			parse(d, frappe.defaultDateFormat, new Date());
			return true;

		}
		catch(e) {
			try{
				parse(d, frappe.defaultDatetimeFormat, new Date());
				return true;
			}
			catch {
				parse(d, frappe.frappe.defaultTimeFormat, new Date());
				return true;
			}
		}
		finally{
			return false;
		}
	},

	get_first_day_of_the_week_index() {
		const weekdays = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
		const first_day_of_the_week = frappe.sys_defaults.first_day_of_the_week || "Sunday";
		return weekdays.indexOf(first_day_of_the_week);
	},
});

// Proxy for dateutil and get_today
Object.defineProperties(window, {
	dateutil: {
		get: function () {
			console.warn(
				"Please use `frappe.datetime` instead of `dateutil`. It will be deprecated soon."
			);
			return frappe.datetime;
		},
		configurable: true,
	},
	date: {
		get: function () {
			console.warn(
				"Please use `frappe.datetime` instead of `date`. It will be deprecated soon."
			);
			return frappe.datetime;
		},
		configurable: true,
	},
	get_today: {
		get: function () {
			console.warn(
				"Please use `frappe.datetime.get_today` instead of `get_today`. It will be deprecated soon."
			);
			return frappe.datetime.get_today;
		},
		configurable: true,
	},
});
