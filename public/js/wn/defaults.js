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
}