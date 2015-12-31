function prettyDate(time, mini){

	if(moment) {
		if(window.sys_defaults && sys_defaults.time_zone) {
			var ret = moment.tz(time, sys_defaults.time_zone).fromNow(mini);
		} else {
			var ret = moment(time).fromNow(mini);
		}
		if(mini) {
			if(ret === "a few seconds") {
				ret = "now";
			} else {
				var parts = ret.split(" ");
				if(parts.length > 1) {
					if(parts[0]==="a" || parts[0]==="an") {
						parts[0] = 1;
					}
					ret = parts[0] + " " + parts[1].substr(0, 1);
				}
			}
		}
		return ret;
	} else {
		if(!time) return ''
		var date = time;
		if(typeof(time)=="string")
			date = new Date((time || "").replace(/-/g,"/").replace(/[TZ]/g," ").replace(/\.[0-9]*/, ""));

		var diff = (((new Date()).getTime() - date.getTime()) / 1000),
		day_diff = Math.floor(diff / 86400);

		if ( isNaN(day_diff) || day_diff < 0 )
			return '';

		return when = day_diff == 0 && (
				diff < 60 && "just now" ||
				diff < 120 && "1 minute ago" ||
				diff < 3600 && Math.floor( diff / 60 ) + " minutes ago" ||
				diff < 7200 && "1 hour ago" ||
				diff < 86400 && Math.floor( diff / 3600 ) + " hours ago") ||
			day_diff == 1 && "Yesterday" ||
			day_diff < 7 && day_diff + " days ago" ||
			day_diff < 31 && Math.ceil( day_diff / 7 ) + " weeks ago" ||
			day_diff < 365 && Math.ceil( day_diff / 30) + " months ago" ||
			"> " + Math.floor( day_diff / 365 ) + " year(s) ago";
	}
}


var comment_when = function(datetime, mini) {
	var timestamp = frappe.datetime.str_to_user ?
		frappe.datetime.str_to_user(datetime) : datetime;
	return '<span class="frappe-timestamp '
			+(mini ? " mini" : "" ) + '" data-timestamp="'+datetime
		+'" title="'+timestamp+'">'
		+ prettyDate(datetime, mini) + '</span>';
};

frappe.provide("frappe.datetime");
frappe.datetime.refresh_when = function() {
	if(jQuery) {
		$(".frappe-timestamp").each(function() {
			$(this).html(prettyDate($(this).attr("data-timestamp"), $(this).hasClass("mini")));
		});
	}
}

setInterval(function() { frappe.datetime.refresh_when() }, 60000); // refresh every minute
