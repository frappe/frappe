// moment strings for translation

function prettyDate(time, mini) {
	if (!time) {
		time = new Date();
	}
	if (moment) {
		if (frappe.sys_defaults && frappe.sys_defaults.time_zone) {
			var ret = moment.tz(time, frappe.sys_defaults.time_zone).locale(frappe.boot.lang).fromNow(mini);
		} else {
			var ret = moment(time).locale(frappe.boot.lang).fromNow(mini);
		}
		if (mini) {
			if (ret === moment().locale(frappe.boot.lang).fromNow(mini)) {
				ret = __("now");
			} else {
				var parts = ret.split(" ");
				if (parts.length > 1) {
					if (parts[0] === "a" || parts[0] === "an") {
						parts[0] = 1;
					}
					if (parts[1].substr(0, 2) === "mo") {
						ret = parts[0] + " M";
					} else {
						ret = parts[0] + " " + parts[1].substr(0, 1);
					}
				}
			}
			ret = ret.substr(0, 5);
		}
		return ret;
	} else {
		if (!time) return ''
		var date = time;
		if (typeof (time) == "string")
			date = new Date((time || "").replace(/-/g, "/").replace(/[TZ]/g, " ").replace(/\.[0-9]*/, ""));

		var diff = (((new Date()).getTime() - date.getTime()) / 1000),
			day_diff = Math.floor(diff / 86400);

		if (isNaN(day_diff) || day_diff < 0)
			return '';

		var when = day_diff == 0 && (
			diff < 60 && __("just now") ||
			diff < 120 && __("1 minute ago") ||
			diff < 3600 && __("{0} minutes ago", [Math.floor(diff / 60)]) ||
			diff < 7200 && __("1 hour ago") ||
			diff < 86400 && ("{0} hours ago", [Math.floor(diff / 3600)])) ||
			day_diff == 1 && __("Yesterday") ||
			day_diff < 7 && __("{0} days ago", day_diff) ||
			day_diff < 31 && __("{0} weeks ago", [Math.ceil(day_diff / 7)]) ||
			day_diff < 365 && __("{0} months ago", [Math.ceil(day_diff / 30)]) ||
			__("> {0} year(s) ago", [Math.floor(day_diff / 365)]);

		return when;
	}
}


var comment_when = function (datetime, mini) {
	var timestamp = frappe.datetime.str_to_user ?
		frappe.datetime.str_to_user(datetime) : datetime;
	return '<span class="frappe-timestamp '
		+ (mini ? " mini" : "") + '" data-timestamp="' + datetime
		+ '" title="' + timestamp + '">'
		+ prettyDate(datetime, mini) + '</span>';
};

frappe.provide("frappe.datetime");
frappe.datetime.refresh_when = function () {
	if (jQuery) {
		$(".frappe-timestamp").each(function () {
			$(this).html(prettyDate($(this).attr("data-timestamp"), $(this).hasClass("mini")));
		});
	}
}

setInterval(function () { frappe.datetime.refresh_when() }, 60000); // refresh every minute
