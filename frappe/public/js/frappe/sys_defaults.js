// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.defaults");

Object.assign(frappe.defaults, {
	get_global_default: function (key) {
		var d = frappe.sys_defaults[key];
		if ($.isArray(d)) d = d[0];
		return d;
	},
	get_global_defaults: function (key) {
		var d = frappe.sys_defaults[key];
		if (!$.isArray(d)) d = [d];
		return d;
	},
	is_enabled: function (key) {
		return cint(this.get_global_default(key)) === 1;
	},
	get_default: function (key) {
		return this.get_global_default(key);
	},
	get_user_default: function (key) {
		return this.get_global_default(key);
	},
});
