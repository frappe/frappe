// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.defaults = {
	get_user_default: function(key) {
		var d = wn.boot.profile.defaults[key];
		if($.isArray(d)) d = d[0];
		return d;
	},
	get_user_defaults: function(key) {
		var d = wn.boot.profile.defaults[key];
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
			
		wn.boot.profile.defaults[key] = value;
		return wn.call({
			method: "webnotes.client.set_default",
			args: {
				key: key,
				value: value
			},
			callback: callback || function(r) {}
		});
	},
	get_default: function(key) {
		var value = wn.boot.profile.defaults[key];
		if(value) {
			try {
				return JSON.parse(value)
			} catch(e) {
				return value;
			}			
		}
	},
}