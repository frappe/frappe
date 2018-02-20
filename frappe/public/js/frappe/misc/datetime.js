// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.datetime');

moment.defaultDateFormat = "YYYY-MM-DD";
moment.defaultTimeFormat = "HH:mm:ss";
moment.defaultDatetimeFormat = moment.defaultDateFormat + " " + moment.defaultTimeFormat;
moment.defaultFormat = moment.defaultDateFormat;

frappe.provide("frappe.datetime");

$.extend(frappe.datetime, {
	convert_to_user_tz: function(date, format) {
		// format defaults to true
		if(frappe.sys_defaults.time_zone) {
			var date_obj = moment.tz(date, frappe.sys_defaults.time_zone).local();
		} else {
			var date_obj = moment(date);
		}

		return (format===false) ? date_obj : date_obj.format(moment.defaultDatetimeFormat);
	},

	convert_to_system_tz: function(date, format) {
		// format defaults to true

		if(frappe.sys_defaults.time_zone) {
			var date_obj = moment(date).tz(frappe.sys_defaults.time_zone);
		} else {
			var date_obj = moment(date);
		}

		return (format===false) ? date_obj : date_obj.format(moment.defaultDatetimeFormat);
	},

	is_timezone_same: function() {
		if(frappe.sys_defaults.time_zone) {
			return moment().tz(frappe.sys_defaults.time_zone).utcOffset() === moment().utcOffset();
		} else {
			return true;
		}
	},

	str_to_obj: function(d) {
		return moment(d, moment.defaultDatetimeFormat)._d;
	},

	obj_to_str: function(d) {
		return moment(d).locale("en").format();
	},

	obj_to_user: function(d) {
		return moment(d).format(frappe.datetime.get_user_fmt().toUpperCase());
	},

	get_diff: function(d1, d2) {
		return moment(d1).diff(d2, "days");
	},

	get_hour_diff: function(d1, d2) {
		return moment(d1).diff(d2, "hours");
	},

	get_day_diff: function(d1, d2) {
		return moment(d1).diff(d2, "days");
	},

	add_days: function(d, days) {
		return moment(d).add(days, "days").format();
	},

	add_months: function(d, months) {
		return moment(d).add(months, "months").format();
	},

	month_start: function() {
		return moment().startOf("month").format();
	},

	month_end: function() {
		return moment().endOf("month").format();
	},

	year_start: function(){
		return moment().startOf("year").format();
	},

	year_end: function(){
		return moment().endOf("year").format();
	},

	get_user_fmt: function() {
		return frappe.sys_defaults.date_format || "yyyy-mm-dd";
	},

	str_to_user: function(val, only_time = false) {
		if(!val) return "";

		if(only_time) {
			return moment(val, moment.defaultTimeFormat)
				.format(moment.defaultTimeFormat);
		}

		var user_fmt = frappe.datetime.get_user_fmt().toUpperCase();
		if(typeof val !== "string" || val.indexOf(" ")===-1) {
			return moment(val).format(user_fmt);
		} else {
			return moment(val, "YYYY-MM-DD HH:mm:ss").format(user_fmt + " HH:mm:ss");
		}
	},

	get_datetime_as_string: function(d) {
		return moment(d).format("YYYY-MM-DD HH:mm:ss");
	},

	user_to_str: function(val, only_time = false) {

		if(only_time) {
			return moment(val, moment.defaultTimeFormat)
				.format(moment.defaultTimeFormat);
		}

		var user_fmt = frappe.datetime.get_user_fmt().toUpperCase();
		var system_fmt = "YYYY-MM-DD";

		if(val.indexOf(" ")!==-1) {
			user_fmt += " HH:mm:ss";
			system_fmt += " HH:mm:ss";
		}

		// user_fmt.replace("YYYY", "YY")? user might only input 2 digits of the year, which should also be parsed
		return moment(val, [user_fmt.replace("YYYY", "YY"),
			user_fmt]).locale("en").format(system_fmt);
	},

	user_to_obj: function(d) {
		return frappe.datetime.str_to_obj(frappe.datetime.user_to_str(d));
	},

	global_date_format: function(d) {
		var m = moment(d);
		if(m._f && m._f.indexOf("HH")!== -1) {
			return m.format("Do MMMM YYYY, h:mma")
		} else {
			return m.format('Do MMMM YYYY');
		}
	},

	now_date: function(as_obj = false) {
		return frappe.datetime._date(moment.defaultDateFormat, as_obj);
	},

	now_time: function(as_obj = false) {
		return frappe.datetime._date(moment.defaultTimeFormat, as_obj);
	},

	now_datetime: function(as_obj = false) {
		return frappe.datetime._date(moment.defaultDatetimeFormat, as_obj);
	},

	_date: function(format, as_obj = false) {
		const { time_zone } = frappe.sys_defaults;
		let date;
		if (time_zone) {
			date = moment.tz(time_zone);
		} else {
			date = moment();
		}
		if (as_obj) {
			return frappe.datetime.moment_to_date_obj(date);
		} else {
			return date.format(format);
		}
	},

	moment_to_date_obj: function(moment) {
		const date_obj = new Date();
		const date_array = moment.toArray();
		date_obj.setFullYear(date_array[0]);
		date_obj.setMonth(date_array[1]);
		date_obj.setDate(date_array[2]);
		date_obj.setHours(date_array[3]);
		date_obj.setMinutes(date_array[4]);
		date_obj.setSeconds(date_array[5]);
		date_obj.setMilliseconds(date_array[6]);
		return date_obj;
	},

	nowdate: function() {
		return frappe.datetime.now_date();
	},

	get_today: function() {
		return frappe.datetime.now_date();
	},

	validate: function(d) {
		return moment(d, [
			moment.defaultDateFormat,
			moment.defaultDatetimeFormat,
			moment.defaultTimeFormat
		], true).isValid();
	},

});

// Proxy for dateutil and get_today
Object.defineProperties(window, {
	'dateutil': {
		get: function() {
			console.warn('Please use `frappe.datetime` instead of `dateutil`. It will be deprecated soon.');
			return frappe.datetime;
		}
	},
	'date': {
		get: function() {
			console.warn('Please use `frappe.datetime` instead of `date`. It will be deprecated soon.');
			return frappe.datetime;
		}
	},
	'get_today': {
		get: function() {
			console.warn('Please use `frappe.datetime.get_today` instead of `get_today`. It will be deprecated soon.');
			return frappe.datetime.get_today;
		}
	}
});
