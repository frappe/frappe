// route urls to their virtual pages

wn.route = function() {
	var route = window.location.hash;
	wn._cur_route = location.hash;

	if(route.substr(0,1)=='#') route = route.substr(1);
	if(route.substr(0,1)=='!') route = route.substr(1);	

	route = $.map(route.split('/'), function(r) { return decodeURIComponent(r); });
	
	switch (route[0]) {
		case "List":
			wn.views.doclistview.show(route[1]);
			break;
		case "Form":
			if(route.length>3) {
				route[2] = route.splice(2).join('/');
			}
			wn.views.formview.show(route[1], route[2]);
			break;
		case "Report":
			wn.views.reportview.show(route[1], route[2]);
			break;
		default:
			wn.views.pageview.show(route[0]);
	}
}

wn.set_route = function(route) {
	window.location.hash = route;
}

wn._cur_route = null;

$(window).bind('hashchange', function() {
	if(location.hash==wn._cur_route)
		return;	
	wn.route();
	
	// analytics code
	if(wn.boot.analytics_code) {
		try {
			eval(wn.boot.analytics_code);
		} catch (e) {
			console.log(e);
		}
	}
});