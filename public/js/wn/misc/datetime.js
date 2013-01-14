wn.provide('wn.datetime');

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
		var d = new Date();
		return [d.getFullYear(), d.getMonth()+1, d.getDate()].join("-") + " " 
			+ [d.getHours(), d.getMinutes(), d.getSeconds()].join(":")
	},
	now_time: function() {
		var d = new Date();
		return [d.getHours(), d.getMinutes(), d.getSeconds()].join(":")
	}
	
});