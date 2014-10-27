// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.datetime');

moment.defaultFormat = "YYYY-MM-DD";
moment.defaultDatetimeFormat = "YYYY-MM-DD HH:mm:ss"
frappe.provide("frappe.datetime");

$.extend(frappe.datetime, {
	str_to_obj: function(d) {
		return moment(d, "YYYY-MM-DD HH:mm:ss")._d;
	},

	obj_to_str: function(d) {
		return moment(d).format();
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
		return moment(val, [user_fmt.replace("YYYY", "YY"), user_fmt]).format(system_fmt);
	},

	user_to_obj: function(d) {
		return dateutil.str_to_obj(dateutil.user_to_str(d));
	},

	global_date_format: function(d) {
		return moment(d).format('Do MMMM YYYY');
	},

	get_today: function() {
		return moment().format();
	},

	now_time: function() {
		return moment().format("HH:mm:ss");
	},

	validate: function(d) {
		return moment(d).isValid();
	},

});

// globals (deprecate)
var date = dateutil = frappe.datetime;
var get_today = frappe.datetime.get_today;
