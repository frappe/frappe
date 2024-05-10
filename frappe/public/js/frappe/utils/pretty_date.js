function prettyDate(date, mini) {
	if (!date) return "";

	if (typeof date == "string") {
		date = frappe.datetime.convert_to_user_tz(date);
		date = new Date(
			(date || "")
				.replace(/-/g, "/")
				.replace(/[TZ]/g, " ")
				.replace(/\.[0-9]*/, "")
		);
	}

	let diff =
		(new Date(frappe.datetime.now_datetime().replace(/-/g, "/")).getTime() - date.getTime()) /
		1000;
	let day_diff = Math.floor(diff / 86400);

	if (isNaN(day_diff) || day_diff < 0) return "";

	if (mini) {
		// Return short format of time difference
		if (day_diff == 0) {
			if (diff < 60) {
				return __("now");
			} else if (diff < 3600) {
				return __("{0} m", [Math.floor(diff / 60)]);
			} else if (diff < 86400) {
				return __("{0} h", [Math.floor(diff / 3600)]);
			}
		} else {
			if (day_diff < 7) {
				return __("{0} d", [day_diff]);
			} else if (day_diff < 31) {
				return __("{0} w", [Math.floor(day_diff / 7)]);
			} else if (day_diff < 365) {
				return __("{0} M", [Math.floor(day_diff / 30)]);
			} else {
				return __("{0} y", [Math.floor(day_diff / 365)]);
			}
		}
	} else {
		// Return long format of time difference
		if (day_diff == 0) {
			if (diff < 60) {
				return __("just now");
			} else if (diff < 120) {
				return __("1 minute ago");
			} else if (diff < 3600) {
				return __("{0} minutes ago", [Math.floor(diff / 60)]);
			} else if (diff < 7200) {
				return __("1 hour ago");
			} else if (diff < 86400) {
				return __("{0} hours ago", [Math.floor(diff / 3600)]);
			}
		} else {
			if (day_diff == 1) {
				return __("yesterday");
			} else if (day_diff < 7) {
				return __("{0} days ago", [day_diff]);
			} else if (day_diff < 14) {
				return __("1 week ago");
			} else if (day_diff < 31) {
				return __("{0} weeks ago", [Math.floor(day_diff / 7)]);
			} else if (day_diff < 62) {
				return __("1 month ago");
			} else if (day_diff < 365) {
				return __("{0} months ago", [Math.floor(day_diff / 30)]);
			} else if (day_diff < 730) {
				return __("1 year ago");
			} else {
				return __("{0} years ago", [Math.floor(day_diff / 365)]);
			}
		}
	}
}

frappe.provide("frappe.datetime");
window.comment_when = function (datetime, mini) {
	var timestamp = frappe.datetime.str_to_user ? frappe.datetime.str_to_user(datetime) : datetime;
	return (
		'<span class="frappe-timestamp ' +
		(mini ? " mini" : "") +
		'" data-timestamp="' +
		datetime +
		'" title="' +
		timestamp +
		'">' +
		prettyDate(datetime, mini) +
		"</span>"
	);
};
frappe.datetime.comment_when = comment_when;
frappe.datetime.prettyDate = prettyDate;

frappe.datetime.refresh_when = function () {
	if (jQuery) {
		$(".frappe-timestamp").each(function () {
			$(this).html(prettyDate($(this).attr("data-timestamp"), $(this).hasClass("mini")));
		});
	}
};

setInterval(function () {
	frappe.datetime.refresh_when();
}, 60000); // refresh every minute
