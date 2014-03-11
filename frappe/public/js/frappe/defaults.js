// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
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
		if(typeof value=="string")
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
	get_restrictions: function() {
		return frappe.defaults.restrictions;
	},
	set_restrictions: function(restrictions) {
		if(!restrictions) return;
		frappe.defaults.restrictions = $.extend(frappe.defaults.restrictions || {}, restrictions);
	}
}