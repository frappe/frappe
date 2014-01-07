function prettyDate(time){
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


var comment_when = function(datetime) {
	return '<span class="wn-timestamp" data-timestamp="'+datetime+'">' + prettyDate(datetime) + '</span>';
};

wn.provide("wn.datetime");
wn.datetime.comment_when = prettyDate;
wn.datetime.refresh_when = function() {
	if(jQuery) {
		$(".wn-timestamp").each(function() {
			$(this).html(prettyDate($(this).attr("data-timestamp")));
		})
	}
}

setInterval(function() { wn.datetime.refresh_when() }, 60000); // refresh every minute
