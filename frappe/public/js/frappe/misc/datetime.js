// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.datetime');

moment.defaultFormat = "YYYY-MM-DD";
moment.defaultDatetimeFormat = "YYYY-MM-DD HH:mm:ss"
frappe.provide("frappe.datetime");

$.extend(frappe.datetime, {
	convert_to_user_tz: function(date, format) {
		// format defaults to true
		if(sys_defaults.time_zone) {
			var date_obj = moment.tz(date, sys_defaults.time_zone).local();
		} else {
			var date_obj = moment(date);
		}

		return (format===false) ? date_obj : date_obj.format(moment.defaultDatetimeFormat);
	},

	convert_to_system_tz: function(date, format) {
		// format defaults to true

		if(sys_defaults.time_zone) {
			var date_obj = moment(date).tz(sys_defaults.time_zone);
		} else {
			var date_obj = moment(date);
		}

		return (format===false) ? date_obj : date_obj.format(moment.defaultDatetimeFormat);
	},

	is_timezone_same: function() {
		if(sys_defaults.time_zone) {
			return moment().tz(sys_defaults.time_zone).utcOffset() === moment().utcOffset();
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
		return moment(d).format(dateutil.get_user_fmt().toUpperCase());
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
		return sys_defaults.date_format || "yyyy-mm-dd";
	},

	str_to_user: function(val, no_time_str) {
		if(!val) return "";
		var user_fmt = dateutil.get_user_fmt().toUpperCase();
		if(typeof val !== "string" || val.indexOf(" ")===-1) {
			return moment(val).format(user_fmt);
		} else {
			return moment(val, "YYYY-MM-DD HH:mm:ss").format(user_fmt + " HH:mm:ss");
		}
	},

	now_datetime: function() {
		return moment().format("YYYY-MM-DD HH:mm:ss");
	},

	get_datetime_as_string: function(d) {
		return moment(d).format("YYYY-MM-DD HH:mm:ss");
	},

	user_to_str: function(val, no_time_str) {
		var user_fmt = dateutil.get_user_fmt().toUpperCase();
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
		return dateutil.str_to_obj(dateutil.user_to_str(d));
	},

	global_date_format: function(d) {
		var m = moment(d);
		if(m._f && m._f.indexOf("HH")!== -1) {
			return m.format("Do MMMM YYYY, h:mma")
		} else {
			return m.format('Do MMMM YYYY');
		}
	},

	get_today: function() {
		return moment().locale("en").format();
	},

	nowdate: function() {
		return frappe.datetime.get_today();
	},

	now_time: function() {
		return frappe.datetime.convert_to_system_tz(moment(), false)
			.locale("en").format("HH:mm:ss");
	},

	validate: function(d) {
		return moment(d).isValid();
	},

});

// globals (deprecate)
var date = dateutil = frappe.datetime;
var get_today = frappe.datetime.get_today;
