// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.provide('wn.datetime');

var double_digit = function(d) {
	if(cint(d)<10) {
		return "0" + cint(d);
	} else {
		return d + "";
	}
}


$.extend(wn.datetime, {
	validate: function(v) {
		if(!v) return;
	
		var time_part = "";
		if(v.indexOf(" ")!=-1) {
			var tmp = v.split(" ");
			v = tmp[0];
			time_part = " " + tmp[1];
		}

		var parts = $.map(v.split('-'), function(part) { return cint(part) ? part : null; });
		if(parts.length!=3) {
			return null;
		}
		var test_date = new Date(parts[0], parts[1]-1, parts[2]);
		if(test_date.getFullYear() !=parts[0] 
			|| (test_date.getMonth() + 1) != parts[1] 
			|| test_date.getDate() != parts[2])
			return null;
	
		return v + time_part;
	},
	now_datetime: function() {
		return wn.datetime.get_datetime_as_string(new Date());
	},
	now_time: function() {
		var d = new Date();
		return [double_digit(d.getHours()), double_digit(d.getMinutes()), double_digit(d.getSeconds())].join(":")
	},
	get_datetime_as_string: function(d) {
		if(!d) return null;
		return [d.getFullYear(), double_digit(d.getMonth()+1), double_digit(d.getDate())].join("-") + " " 
			+ [double_digit(d.getHours()), double_digit(d.getMinutes()), double_digit(d.getSeconds())].join(":");
	}
});