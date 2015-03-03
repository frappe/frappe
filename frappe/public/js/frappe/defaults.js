// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.defaults = {
	get_user_default: function(key) {
		var d = frappe.boot.user.defaults[key];
		if($.isArray(d)) d = d[0];
		return d;
	},
	get_user_defaults: function(key) {
		var d = frappe.boot.user.defaults[key];
		if(!$.isArray(d)) d = [d];
		return d;
	},
	get_global_default: function(key) {
		var d = sys_defaults[key];
		if($.isArray(d)) d = d[0];
		return d;
	},
	get_global_defaults: function(key) {
		var d = sys_defaults[key];
		if(!$.isArray(d)) d = [d];
		return d;
	},
	set_default: function(key, value, callback) {
		if(typeof value!=="string")
			value = JSON.stringify(value);

		frappe.boot.user.defaults[key] = value;
		return frappe.call({
			method: "frappe.client.set_default",
			args: {
				key: key,
				value: value
			},
			callback: callback || function(r) {}
		});
	},
	get_default: function(key) {
		var value = frappe.boot.user.defaults[key];
		if(value) {
			try {
				return JSON.parse(value)
			} catch(e) {
				return value;
			}
		}
	},
	get_user_permissions: function() {
		return frappe.defaults.user_permissions;
	},
	set_user_permissions: function(user_permissions) {
		if(!user_permissions) return;
		frappe.defaults.user_permissions = $.extend(frappe.defaults.user_permissions || {}, user_permissions);
	}
}
