// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.defaults = {
	get_user_default: function(key) {
		var defaults = frappe.boot.user.defaults;
		var d = defaults[key];
		if(!d && frappe.defaults.is_a_user_permission_key(key))
			d = defaults[frappe.model.scrub(key)];
		if($.isArray(d)) d = d[0];
		return d;
	},
	get_user_defaults: function(key) {
		var defaults = frappe.boot.user.defaults;
		var d = defaults[key];

		if (frappe.defaults.is_a_user_permission_key(key)) {
			if (d && $.isArray(d) && d.length===1) {
				// Use User Permission value when only when it has a single value
				d = d[0];
			} else {
				d = defaults[key] || defaults[frappe.model.scrub(key)];
			}
		}
		if(!$.isArray(d)) d = [d];
		return d;
	},
	get_global_default: function(key) {
		var d = frappe.sys_defaults[key];
		if($.isArray(d)) d = d[0];
		return d;
	},
	get_global_defaults: function(key) {
		var d = frappe.sys_defaults[key];
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
	set_user_default_local: function(key, value) {
		frappe.boot.user.defaults[key] = value;
	},
	get_default: function(key) {
		var defaults = frappe.boot.user.defaults;
		var value = defaults[key];
		if (frappe.defaults.is_a_user_permission_key(key)) {
			if (value && $.isArray(value) && value.length===1) {
				value = value[0];
			} else {
				value = defaults[frappe.model.scrub(key)];
			}
		}

		if(value) {
			try {
				return JSON.parse(value)
			} catch(e) {
				return value;
			}
		}
	},

	is_a_user_permission_key: function(key) {
		return key.indexOf(":")===-1 && key !== frappe.model.scrub(key);
	},

	get_user_permissions: function() {
		return frappe.boot.user_permissions;
	},
}
